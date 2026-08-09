from __future__ import annotations

import html
import io
import json
import math
import re
import shutil
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_text


ASCII_BOX_HORIZONTAL = "-"
ASCII_BOX_VERTICAL = "|"
ASCII_CORNER = "+"
ASCII_ARROW_DOWN = "v"
ASCII_ARROW_RIGHT = ">"
DEFAULT_DIRECTION = "TB"

# Current ComfyUI frontend Nodes 2.0 dark-theme design tokens.
# Source reference: Comfy-Org/ComfyUI_frontend design-system style.css/_palette.css.
COMFY_V2_DARK = {
    "background": "#262729",       # charcoal-600 / component-node-background
    "header": "#202121",           # charcoal-700 / node-component-header-surface
    "border": "#55565e",           # charcoal-100 / component-node-border
    "widget": "#313235",           # charcoal-400 / secondary hover surface
    "text": "#ffffff",
    "muted": "#a0a0a0",            # smoke-700 / slot text
    "divider": "#2d2e32",          # charcoal-500
    "outline": "#171718",          # charcoal-800
}


@dataclass(frozen=True)
class FlowNode:
    id: str
    label: str
    shape: str = "box"


@dataclass(frozen=True)
class FlowEdge:
    source: str
    target: str
    label: str = ""


@dataclass
class Box:
    node: FlowNode
    x: int
    y: int
    width: int
    height: int


def _safe_slug(value: str, fallback: str = "diagram") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-._")
    return text[:96] or fallback


def _load_json_value(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    path = Path(text).expanduser()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def normalize_flow_spec(value: str | dict[str, Any]) -> tuple[list[FlowNode], list[FlowEdge], str]:
    data = _load_json_value(value)
    raw_nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    raw_edges = data.get("edges") if isinstance(data.get("edges"), list) else []
    direction = str(data.get("direction") or DEFAULT_DIRECTION).upper()
    if direction not in {"TB", "LR"}:
        direction = DEFAULT_DIRECTION

    nodes: list[FlowNode] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_nodes):
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or f"node-{index + 1}").strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        label = str(item.get("label") or item.get("title") or node_id).strip() or node_id
        shape = str(item.get("shape") or "box").strip().lower()
        nodes.append(FlowNode(node_id, label, shape))

    edges: list[FlowEdge] = []
    for item in raw_edges:
        if not isinstance(item, dict):
            continue
        source = str(item.get("from") or item.get("source") or "").strip()
        target = str(item.get("to") or item.get("target") or "").strip()
        if source not in seen or target not in seen or source == target:
            continue
        edges.append(FlowEdge(source, target, str(item.get("label") or "").strip()))

    if not nodes:
        raise ValueError("Flowchart spec has no valid nodes.")
    return nodes, edges, direction


def _wrapped_label(label: str, max_width: int = 28) -> list[str]:
    source_lines = str(label or "").splitlines() or [""]
    result: list[str] = []
    for source in source_lines:
        words = source.split()
        if not words:
            result.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if len(candidate) <= max_width:
                current = candidate
            else:
                result.append(current[:max_width])
                current = word
        result.append(current[:max_width])
    return result[:6] or [""]


def _assign_layers(nodes: list[FlowNode], edges: list[FlowEdge]) -> dict[str, int]:
    """Deterministic hierarchical layers.

    DAGs use longest-path topological layering. Cyclic graphs use PHART-style BFS depth
    from source-like roots so the principal flow remains readable and cycle/back edges can
    be routed around the outside instead of collapsing an entire SCC into one row.
    """
    ids = [node.id for node in nodes]
    declared = {node_id: index for index, node_id in enumerate(ids)}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in ids}
    indegree = {node_id: 0 for node_id in ids}
    for edge in edges:
        if edge.target not in adjacency[edge.source]:
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1
    for values in adjacency.values():
        values.sort(key=lambda node_id: declared[node_id])

    work_indegree = dict(indegree)
    queue = deque(node_id for node_id in ids if work_indegree[node_id] == 0)
    layers = {node_id: 0 for node_id in ids}
    visited: list[str] = []
    while queue:
        current = queue.popleft()
        visited.append(current)
        for target in adjacency[current]:
            layers[target] = max(layers[target], layers[current] + 1)
            work_indegree[target] -= 1
            if work_indegree[target] == 0:
                queue.append(target)
    if len(visited) == len(ids):
        return layers

    roots = [node_id for node_id in ids if indegree[node_id] == 0] or [ids[0]]
    assigned: set[str] = set()
    frontier = deque((node_id, 0) for node_id in roots)
    while frontier:
        current, depth = frontier.popleft()
        if current in assigned:
            continue
        assigned.add(current)
        layers[current] = depth
        for target in adjacency[current]:
            if target not in assigned:
                frontier.append((target, depth + 1))

    # Disconnected cyclic components get their own deterministic BFS roots after the main
    # component. This avoids arbitrary one-node-per-layer fallback behaviour.
    next_base = max((layers[node_id] for node_id in assigned), default=-1) + 1
    for node_id in ids:
        if node_id in assigned:
            continue
        frontier = deque([(node_id, next_base)])
        while frontier:
            current, depth = frontier.popleft()
            if current in assigned:
                continue
            assigned.add(current)
            layers[current] = depth
            for target in adjacency[current]:
                if target not in assigned:
                    frontier.append((target, depth + 1))
        next_base = max(layers.values(), default=next_base) + 1
    return layers


def _ordered_layers(
    nodes: list[FlowNode],
    edges: list[FlowEdge],
) -> tuple[dict[str, int], dict[int, list[FlowNode]]]:
    """Reduce crossings with stable barycentric sweeps inside fixed layers."""
    layers = _assign_layers(nodes, edges)
    declared = {node.id: index for index, node in enumerate(nodes)}
    predecessors: dict[str, list[str]] = defaultdict(list)
    successors: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        predecessors[edge.target].append(edge.source)
        successors[edge.source].append(edge.target)

    grouped: dict[int, list[FlowNode]] = defaultdict(list)
    for node in nodes:
        grouped[layers[node.id]].append(node)
    layer_numbers = sorted(grouped)

    def sweep(numbers: list[int], neighbours: dict[str, list[str]]) -> None:
        positions = {
            node.id: index
            for layer in layer_numbers
            for index, node in enumerate(grouped[layer])
        }
        for layer in numbers:
            scored: list[tuple[float, int, FlowNode]] = []
            for node in grouped[layer]:
                values = [
                    positions[other]
                    for other in neighbours.get(node.id, [])
                    if other in positions and layers.get(other) != layer
                ]
                score = sum(values) / len(values) if values else float(declared[node.id])
                scored.append((score, declared[node.id], node))
            grouped[layer] = [item[2] for item in sorted(scored, key=lambda item: (item[0], item[1]))]
            for index, node in enumerate(grouped[layer]):
                positions[node.id] = index

    for _ in range(4):
        sweep(layer_numbers[1:], predecessors)
        sweep(list(reversed(layer_numbers[:-1])), successors)
    return layers, {layer: list(grouped[layer]) for layer in layer_numbers}


def _layout(nodes: list[FlowNode], edges: list[FlowEdge], direction: str) -> tuple[dict[str, Box], int, int]:
    layers, grouped = _ordered_layers(nodes, edges)

    sizes: dict[str, tuple[int, int]] = {}
    for node in nodes:
        lines = _wrapped_label(node.label, max_width=30)
        width = max(12, max((len(line) for line in lines), default=0) + 4)
        # Odd widths give every box a real integer center cell, avoiding tiny zig-zags in
        # otherwise straight vertical chains.
        if width % 2 == 0:
            width += 1
        height = max(3, len(lines) + 2)
        sizes[node.id] = (width, height)

    # Count edges that need lanes between adjacent layers and leave enough rows/columns for
    # them. This is the same principle as PHART's tunable layer_spacing, but automatic.
    boundary_load: dict[int, int] = defaultdict(int)
    for edge in edges:
        source_layer, target_layer = layers[edge.source], layers[edge.target]
        if target_layer == source_layer + 1:
            boundary_load[source_layer] += 1
    layer_gap = max(7, min(18, max(boundary_load.values(), default=1) + 4))
    node_gap = 8
    outer_margin = max(5, 3 + sum(1 for edge in edges if layers[edge.target] <= layers[edge.source]))

    boxes: dict[str, Box] = {}
    if direction == "LR":
        x = outer_margin
        max_total_height = max(
            (
                sum(sizes[node.id][1] for node in layer_nodes)
                + max(0, len(layer_nodes) - 1) * node_gap
                for layer_nodes in grouped.values()
            ),
            default=1,
        )
        for layer in sorted(grouped):
            layer_nodes = grouped[layer]
            total_height = (
                sum(sizes[node.id][1] for node in layer_nodes)
                + max(0, len(layer_nodes) - 1) * node_gap
            )
            y = outer_margin + max(0, (max_total_height - total_height) // 2)
            layer_width = max(sizes[node.id][0] for node in layer_nodes)
            for node in layer_nodes:
                width, height = sizes[node.id]
                boxes[node.id] = Box(node, x, y, width, height)
                y += height + node_gap
            x += layer_width + layer_gap
    else:
        y = outer_margin
        max_total_width = max(
            (
                sum(sizes[node.id][0] for node in layer_nodes)
                + max(0, len(layer_nodes) - 1) * node_gap
                for layer_nodes in grouped.values()
            ),
            default=1,
        )
        for layer in sorted(grouped):
            layer_nodes = grouped[layer]
            total_width = (
                sum(sizes[node.id][0] for node in layer_nodes)
                + max(0, len(layer_nodes) - 1) * node_gap
            )
            x = outer_margin + max(0, (max_total_width - total_width) // 2)
            layer_height = max(sizes[node.id][1] for node in layer_nodes)
            for node in layer_nodes:
                width, height = sizes[node.id]
                boxes[node.id] = Box(node, x, y, width, height)
                x += width + node_gap
            y += layer_height + layer_gap

    canvas_width = max((box.x + box.width for box in boxes.values()), default=0) + outer_margin + 1
    canvas_height = max((box.y + box.height for box in boxes.values()), default=0) + outer_margin + 1
    return boxes, canvas_width, canvas_height


def _port_positions(start: int, span: int, count: int) -> list[int]:
    if count <= 1:
        return [start + span // 2]
    usable = max(1, span - 2)
    return [
        start + min(span - 2, max(1, 1 + round((index + 1) * usable / (count + 1))))
        for index in range(count)
    ]


def _edge_class(edge: FlowEdge, layers: dict[str, int]) -> str:
    source_layer, target_layer = layers[edge.source], layers[edge.target]
    if target_layer > source_layer:
        return "forward"
    if target_layer < source_layer:
        return "back"
    return "same"


def _outer_side(
    edge: FlowEdge,
    boxes: dict[str, Any],
    direction: str,
) -> str:
    """Choose the exterior side that does not run through peer nodes."""
    source, target = boxes[edge.source], boxes[edge.target]
    if direction == "TB":
        source_center = source.x + source.width / 2
        target_center = target.x + target.width / 2
        return "right" if source_center >= target_center else "left"
    source_center = source.y + source.height / 2
    target_center = target.y + target.height / 2
    return "bottom" if source_center >= target_center else "top"


def _ascii_ports(
    boxes: dict[str, Box],
    edges: list[FlowEdge],
    layers: dict[str, int],
    direction: str,
) -> dict[int, tuple[tuple[int, int], tuple[int, int]]]:
    """Assign distinct face ports, PHART shared_ports=none style."""
    source_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    target_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        kind = _edge_class(edge, layers)
        side = _outer_side(edge, boxes, direction) if kind != "forward" else "forward"
        source_groups[(edge.source, kind, side)].append(index)
        target_groups[(edge.target, kind, side)].append(index)

    result: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
    for (node_id, kind, side), indexes in source_groups.items():
        box = boxes[node_id]
        if direction == "TB":
            if kind == "forward":
                points = [(value, box.y + box.height) for value in _port_positions(box.x, box.width, len(indexes))]
            elif side == "right":
                points = [(box.x + box.width, value) for value in _port_positions(box.y, box.height, len(indexes))]
            elif side == "left":
                points = [(box.x - 1, value) for value in _port_positions(box.y, box.height, len(indexes))]
            else:
                points = [(value, box.y - 1) for value in _port_positions(box.x, box.width, len(indexes))]
        else:
            if kind == "forward":
                points = [(box.x + box.width, value) for value in _port_positions(box.y, box.height, len(indexes))]
            elif side == "bottom":
                points = [(value, box.y + box.height) for value in _port_positions(box.x, box.width, len(indexes))]
            elif side == "top":
                points = [(value, box.y - 1) for value in _port_positions(box.x, box.width, len(indexes))]
            else:
                points = [(box.x - 1, value) for value in _port_positions(box.y, box.height, len(indexes))]
        for index, point in zip(indexes, points):
            result[index] = (point, result.get(index, ((0, 0), (0, 0)))[1])

    for (node_id, kind, side), indexes in target_groups.items():
        box = boxes[node_id]
        if direction == "TB":
            if kind == "forward":
                points = [(value, box.y - 1) for value in _port_positions(box.x, box.width, len(indexes))]
            elif side == "right":
                points = [(box.x + box.width, value) for value in _port_positions(box.y, box.height, len(indexes))]
            elif side == "left":
                points = [(box.x - 1, value) for value in _port_positions(box.y, box.height, len(indexes))]
            else:
                points = [(value, box.y - 1) for value in _port_positions(box.x, box.width, len(indexes))]
        else:
            if kind == "forward":
                points = [(box.x - 1, value) for value in _port_positions(box.y, box.height, len(indexes))]
            elif side == "bottom":
                points = [(value, box.y + box.height) for value in _port_positions(box.x, box.width, len(indexes))]
            elif side == "top":
                points = [(value, box.y - 1) for value in _port_positions(box.x, box.width, len(indexes))]
            else:
                points = [(box.x - 1, value) for value in _port_positions(box.y, box.height, len(indexes))]
        for index, point in zip(indexes, points):
            result[index] = (result.get(index, ((0, 0), (0, 0)))[0], point)
    return result


def _compress_route(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for point in points:
        if result and point == result[-1]:
            continue
        result.append(point)
    return result


def _ascii_routes(
    boxes: dict[str, Box],
    edges: list[FlowEdge],
    layers: dict[str, int],
    direction: str,
    canvas_width: int,
    canvas_height: int,
) -> list[list[tuple[int, int]]]:
    ports = _ascii_ports(boxes, edges, layers, direction)
    adjacent_by_boundary: dict[int, list[int]] = defaultdict(list)
    back_indexes: list[int] = []
    same_indexes: list[int] = []
    for index, edge in enumerate(edges):
        kind = _edge_class(edge, layers)
        if kind == "forward" and layers[edge.target] == layers[edge.source] + 1:
            adjacent_by_boundary[layers[edge.source]].append(index)
        elif kind == "back":
            back_indexes.append(index)
        elif kind == "same":
            same_indexes.append(index)

    lane_for: dict[int, int] = {}
    for boundary, indexes in adjacent_by_boundary.items():
        if direction == "TB":
            source_bottom = max(
                box.y + box.height
                for box in boxes.values()
                if layers[box.node.id] == boundary
            )
            target_top = min(
                box.y - 1
                for box in boxes.values()
                if layers[box.node.id] == boundary + 1
            )
            available = max(1, target_top - source_bottom)
            for lane_index, edge_index in enumerate(indexes):
                lane_for[edge_index] = source_bottom + min(
                    available - 1,
                    max(1, round((lane_index + 1) * available / (len(indexes) + 1))),
                )
        else:
            source_right = max(
                box.x + box.width
                for box in boxes.values()
                if layers[box.node.id] == boundary
            )
            target_left = min(
                box.x - 1
                for box in boxes.values()
                if layers[box.node.id] == boundary + 1
            )
            available = max(1, target_left - source_right)
            for lane_index, edge_index in enumerate(indexes):
                lane_for[edge_index] = source_right + min(
                    available - 1,
                    max(1, round((lane_index + 1) * available / (len(indexes) + 1))),
                )

    back_lane = {edge_index: 1 + index for index, edge_index in enumerate(back_indexes)}
    same_lane = {edge_index: 1 + index for index, edge_index in enumerate(same_indexes)}
    routes: list[list[tuple[int, int]]] = []

    for index, edge in enumerate(edges):
        start, end = ports[index]
        kind = _edge_class(edge, layers)
        span = layers[edge.target] - layers[edge.source]

        if kind == "forward" and span == 1:
            lane = lane_for[index]
            points = (
                [start, (start[0], lane), (end[0], lane), end]
                if direction == "TB"
                else [start, (lane, start[1]), (lane, end[1]), end]
            )
        elif kind == "forward":
            # Long forward edges use an exterior lane so they cannot cut through
            # intermediate node layers.
            if direction == "TB":
                lane = canvas_width - 2 - (index % 3)
                points = [start, (start[0], start[1] + 1), (lane, start[1] + 1),
                          (lane, end[1] - 1), (end[0], end[1] - 1), end]
            else:
                lane = canvas_height - 2 - (index % 3)
                points = [start, (start[0] + 1, start[1]), (start[0] + 1, lane),
                          (end[0] - 1, lane), (end[0] - 1, end[1]), end]
        elif kind == "back":
            side = _outer_side(edge, boxes, direction)
            if direction == "TB":
                lane = (
                    canvas_width - 2 - back_lane[index]
                    if side == "right"
                    else back_lane[index]
                )
                points = [start, (lane, start[1]), (lane, end[1]), end]
            else:
                lane = (
                    canvas_height - 2 - back_lane[index]
                    if side == "bottom"
                    else back_lane[index]
                )
                points = [start, (start[0], lane), (end[0], lane), end]
        else:
            # Same-layer edges route around the outside of that row/column.
            if direction == "TB":
                lane = max(1, min(start[1], end[1]) - 2 - same_lane[index])
                points = [start, (start[0], lane), (end[0], lane), end]
            else:
                lane = max(1, min(start[0], end[0]) - 2 - same_lane[index])
                points = [start, (lane, start[1]), (lane, end[1]), end]
        routes.append(_compress_route(points))
    return routes


def _expand_route(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) < 2:
        return points
    result = [points[0]]
    for target in points[1:]:
        x, y = result[-1]
        tx, ty = target
        # Every generated segment is orthogonal. Preserve the segment order so the
        # arrow approaches the target on the intended face.
        if x != tx and y != ty:
            raise ValueError("Non-orthogonal ASCII route segment.")
        while x != tx:
            x += 1 if tx > x else -1
            result.append((x, y))
        while y != ty:
            y += 1 if ty > y else -1
            result.append((x, y))
    return result


def _axis(a: tuple[int, int], b: tuple[int, int]) -> str:
    return "h" if a[1] == b[1] else "v"


def _draw_ascii_route(grid: list[list[str]], points: list[tuple[int, int]]) -> None:
    route = _expand_route(points)
    for index, point in enumerate(route):
        if len(route) == 1:
            continue
        if index == len(route) - 1:
            previous = route[index - 1]
            dx, dy = point[0] - previous[0], point[1] - previous[1]
            _put(grid, point[0], point[1], ">" if dx > 0 else ("<" if dx < 0 else ("v" if dy > 0 else "^")))
            continue
        previous = route[index - 1] if index > 0 else None
        following = route[index + 1]
        axes = {_axis(point, following)}
        if previous is not None:
            axes.add(_axis(previous, point))
        _put(grid, point[0], point[1], "-" if axes == {"h"} else ("|" if axes == {"v"} else "+"))


def _place_edge_label(grid: list[list[str]], points: list[tuple[int, int]], label: str) -> None:
    text = str(label or "").strip()
    if not text:
        return
    rendered = text[:24]
    route = _expand_route(points)
    segments: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for point in route:
        if not current or point[1] == current[-1][1]:
            current.append(point)
        else:
            if len(current) >= len(rendered) + 2:
                segments.append(current)
            current = [point]
    if len(current) >= len(rendered) + 2:
        segments.append(current)

    for segment in sorted(segments, key=len, reverse=True):
        y = segment[0][1] - 1
        left = min(point[0] for point in segment)
        right = max(point[0] for point in segment)
        x = left + max(0, (right - left + 1 - len(rendered)) // 2)
        if y < 0 or x < 0 or x + len(rendered) > len(grid[y]):
            continue
        if any(grid[y][x + offset] != " " for offset in range(len(rendered))):
            continue
        for offset, char in enumerate(rendered):
            grid[y][x + offset] = char
        return


def _put(grid: list[list[str]], x: int, y: int, char: str) -> None:
    if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[y]):
        return
    current = grid[y][x]
    if current == " " or current == char:
        grid[y][x] = char
        return
    if {current, char} <= {"-", "|", "+"}:
        grid[y][x] = "+"
        return
    if char in {">", "<", "^", "v"}:
        grid[y][x] = char


def _line_h(grid: list[list[str]], x1: int, x2: int, y: int) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        _put(grid, x, y, "-")


def _line_v(grid: list[list[str]], x: int, y1: int, y2: int) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        _put(grid, x, y, "|")


def render_flowchart_ascii(value: str | dict[str, Any]) -> str:
    """Render canonical 7-bit ASCII from a semantic graph, never from model spacing."""
    nodes, edges, direction = normalize_flow_spec(value)
    layers = _assign_layers(nodes, edges)
    boxes, width, height = _layout(nodes, edges, direction)
    routes = _ascii_routes(boxes, edges, layers, direction, width, height)
    grid = [[" " for _ in range(max(1, width))] for _ in range(max(1, height))]

    # Edges first. Nodes then mask any accidental edge contact with their own borders.
    for route in routes:
        _draw_ascii_route(grid, route)

    for box in boxes.values():
        x, y, box_width, box_height = box.x, box.y, box.width, box.height
        _put(grid, x, y, "+")
        _put(grid, x + box_width - 1, y, "+")
        _put(grid, x, y + box_height - 1, "+")
        _put(grid, x + box_width - 1, y + box_height - 1, "+")
        for xx in range(x + 1, x + box_width - 1):
            _put(grid, xx, y, "-")
            _put(grid, xx, y + box_height - 1, "-")
        for yy in range(y + 1, y + box_height - 1):
            _put(grid, x, yy, "|")
            _put(grid, x + box_width - 1, yy, "|")

        lines = _wrapped_label(box.node.label, max_width=max(1, box_width - 4))
        start_y = y + max(1, (box_height - len(lines)) // 2)
        for offset, line in enumerate(lines):
            label = line[: box_width - 4]
            start_x = x + max(2, (box_width - len(label)) // 2)
            for char_index, char in enumerate(label):
                if start_x + char_index < x + box_width - 1:
                    grid[start_y + offset][start_x + char_index] = char

    # Arrowheads and edge labels are restored last so a target is unambiguous.
    for edge, route in zip(edges, routes):
        expanded = _expand_route(route)
        if len(expanded) >= 2:
            point, previous = expanded[-1], expanded[-2]
            dx, dy = point[0] - previous[0], point[1] - previous[1]
            _put(grid, point[0], point[1], ">" if dx > 0 else ("<" if dx < 0 else ("v" if dy > 0 else "^")))
        _place_edge_label(grid, route, edge.label)

    rendered = "\n".join("".join(row).rstrip() for row in grid)
    lines = rendered.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines) + "\n"


def _svg_text(x: float, y: float, value: str, size: int = 14, anchor: str = "middle",
              fill: str = "#111827", weight: int = 500) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(value)}</text>'
    )


@dataclass
class VectorBox:
    node: FlowNode
    layer: int
    x: float
    y: float
    width: float
    height: float


def _vector_layout(
    nodes: list[FlowNode],
    edges: list[FlowEdge],
    direction: str,
) -> tuple[dict[str, VectorBox], float, float, dict[str, int]]:
    layers, grouped = _ordered_layers(nodes, edges)
    node_gap = 56.0
    layer_gap = 118.0
    margin = 54.0

    sizes: dict[str, tuple[float, float]] = {}
    for node in nodes:
        lines = _wrapped_label(node.label, max_width=27)
        longest = max((len(line) for line in lines), default=8)
        width = min(330.0, max(160.0, 28.0 + longest * 8.4))
        height = max(72.0, 42.0 + len(lines) * 18.0)
        if node.shape in {"decision", "diamond"}:
            width, height = max(width, 190.0), max(height, 104.0)
        elif node.shape in {"start", "end", "terminal"}:
            width = max(width, 176.0)
        sizes[node.id] = (width, height)

    boxes: dict[str, VectorBox] = {}
    if direction == "LR":
        column_widths = {layer: max(sizes[node.id][0] for node in group) for layer, group in grouped.items()}
        total_heights = {
            layer: sum(sizes[node.id][1] for node in group) + node_gap * max(0, len(group) - 1)
            for layer, group in grouped.items()
        }
        canvas_height = max(total_heights.values(), default=1.0) + margin * 2
        x = margin
        for layer in sorted(grouped):
            y = margin + (canvas_height - margin * 2 - total_heights[layer]) / 2
            for node in grouped[layer]:
                width, height = sizes[node.id]
                boxes[node.id] = VectorBox(node, layer, x, y, width, height)
                y += height + node_gap
            x += column_widths[layer] + layer_gap
        canvas_width = x - layer_gap + margin
    else:
        row_heights = {layer: max(sizes[node.id][1] for node in group) for layer, group in grouped.items()}
        total_widths = {
            layer: sum(sizes[node.id][0] for node in group) + node_gap * max(0, len(group) - 1)
            for layer, group in grouped.items()
        }
        canvas_width = max(total_widths.values(), default=1.0) + margin * 2
        y = margin
        for layer in sorted(grouped):
            x = margin + (canvas_width - margin * 2 - total_widths[layer]) / 2
            for node in grouped[layer]:
                width, height = sizes[node.id]
                boxes[node.id] = VectorBox(node, layer, x, y, width, height)
                x += width + node_gap
            y += row_heights[layer] + layer_gap
        canvas_height = y - layer_gap + margin
    return boxes, canvas_width, canvas_height, layers


def _vector_ports(
    boxes: dict[str, VectorBox],
    edges: list[FlowEdge],
    layers: dict[str, int],
    direction: str,
) -> dict[int, tuple[tuple[float, float], tuple[float, float]]]:
    source_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    target_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        kind = _edge_class(edge, layers)
        side = _outer_side(edge, boxes, direction) if kind != "forward" else "forward"
        source_groups[(edge.source, kind, side)].append(index)
        target_groups[(edge.target, kind, side)].append(index)

    result: dict[int, tuple[tuple[float, float], tuple[float, float]]] = {}

    def values(start: float, span: float, count: int) -> list[float]:
        return [start + span * (index + 1) / (count + 1) for index in range(count)]

    for (node_id, kind, side), indexes in source_groups.items():
        box = boxes[node_id]
        if direction == "TB":
            if kind == "forward":
                points = [(value, box.y + box.height) for value in values(box.x, box.width, len(indexes))]
            elif side == "right":
                points = [(box.x + box.width, value) for value in values(box.y, box.height, len(indexes))]
            elif side == "left":
                points = [(box.x, value) for value in values(box.y, box.height, len(indexes))]
            else:
                points = [(value, box.y) for value in values(box.x, box.width, len(indexes))]
        else:
            if kind == "forward":
                points = [(box.x + box.width, value) for value in values(box.y, box.height, len(indexes))]
            elif side == "bottom":
                points = [(value, box.y + box.height) for value in values(box.x, box.width, len(indexes))]
            elif side == "top":
                points = [(value, box.y) for value in values(box.x, box.width, len(indexes))]
            else:
                points = [(box.x, value) for value in values(box.y, box.height, len(indexes))]
        for index, point in zip(indexes, points):
            result[index] = (point, result.get(index, ((0.0, 0.0), (0.0, 0.0)))[1])

    for (node_id, kind, side), indexes in target_groups.items():
        box = boxes[node_id]
        if direction == "TB":
            if kind == "forward":
                points = [(value, box.y) for value in values(box.x, box.width, len(indexes))]
            elif side == "right":
                points = [(box.x + box.width, value) for value in values(box.y, box.height, len(indexes))]
            elif side == "left":
                points = [(box.x, value) for value in values(box.y, box.height, len(indexes))]
            else:
                points = [(value, box.y) for value in values(box.x, box.width, len(indexes))]
        else:
            if kind == "forward":
                points = [(box.x, value) for value in values(box.y, box.height, len(indexes))]
            elif side == "bottom":
                points = [(value, box.y + box.height) for value in values(box.x, box.width, len(indexes))]
            elif side == "top":
                points = [(value, box.y) for value in values(box.x, box.width, len(indexes))]
            else:
                points = [(box.x, value) for value in values(box.y, box.height, len(indexes))]
        for index, point in zip(indexes, points):
            result[index] = (result.get(index, ((0.0, 0.0), (0.0, 0.0)))[0], point)
    return result


def _vector_edge_points(
    index: int,
    edge: FlowEdge,
    start: tuple[float, float],
    end: tuple[float, float],
    boxes: dict[str, VectorBox],
    layers: dict[str, int],
    width: float,
    height: float,
    direction: str,
) -> list[tuple[float, float]]:
    kind = _edge_class(edge, layers)
    span = layers[edge.target] - layers[edge.source]
    if kind == "forward" and span == 1:
        if direction == "TB":
            middle = (start[1] + end[1]) / 2
            return [start, (start[0], middle), (end[0], middle), end]
        middle = (start[0] + end[0]) / 2
        return [start, (middle, start[1]), (middle, end[1]), end]

    if kind == "forward":
        # Long forward edges use an outer lane to avoid intermediate nodes.
        if direction == "TB":
            lane = width - 28.0 - (index % 6) * 14.0
            return [start, (start[0], start[1] + 28.0), (lane, start[1] + 28.0),
                    (lane, end[1] - 28.0), (end[0], end[1] - 28.0), end]
        lane = height - 28.0 - (index % 6) * 14.0
        return [start, (start[0] + 28.0, start[1]), (start[0] + 28.0, lane),
                (end[0] - 28.0, lane), (end[0] - 28.0, end[1]), end]

    if kind == "back":
        side = _outer_side(edge, boxes, direction)
        if direction == "TB":
            lane = (
                width - 20.0 - (index % 8) * 14.0
                if side == "right"
                else 20.0 + (index % 8) * 14.0
            )
            return [start, (lane, start[1]), (lane, end[1]), end]
        lane = (
            height - 20.0 - (index % 8) * 14.0
            if side == "bottom"
            else 20.0 + (index % 8) * 14.0
        )
        return [start, (start[0], lane), (end[0], lane), end]

    # Same-layer relationship gets an exterior loop.
    if direction == "TB":
        lane = max(20.0, min(start[1], end[1]) - 34.0 - (index % 6) * 12.0)
        return [start, (start[0], lane), (end[0], lane), end]
    lane = max(20.0, min(start[0], end[0]) - 34.0 - (index % 6) * 12.0)
    return [start, (lane, start[1]), (lane, end[1]), end]


def _svg_path(points: list[tuple[float, float]]) -> str:
    return " ".join(
        [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
        + [f"L{x:.1f},{y:.1f}" for x, y in points[1:]]
    )


def _svg_flow_node(box: VectorBox) -> str:
    """Render a real vector node shape with a portable explicit shadow.

    Do not use an SVG filter here: many Markdown/image conversion pipelines disable or
    partially implement filters. A separate translucent shadow primitive keeps the node
    readable in browsers, GitHub previews, converters, and exported documentation.
    """
    x, y, width, height = box.x, box.y, box.width, box.height
    if box.node.shape in {"decision", "diamond"}:
        points = (
            f"{x + width / 2:.1f},{y:.1f} "
            f"{x + width:.1f},{y + height / 2:.1f} "
            f"{x + width / 2:.1f},{y + height:.1f} "
            f"{x:.1f},{y + height / 2:.1f}"
        )
        shadow = (
            f"{x + width / 2:.1f},{y + 4:.1f} "
            f"{x + width:.1f},{y + height / 2 + 4:.1f} "
            f"{x + width / 2:.1f},{y + height + 4:.1f} "
            f"{x:.1f},{y + height / 2 + 4:.1f}"
        )
        return (
            f'<polygon points="{shadow}" fill="#0f172a" opacity="0.10"/>'
            f'<polygon points="{points}" fill="url(#node-fill)" stroke="#64748b" stroke-width="1.7"/>'
        )
    radius = height / 2 if box.node.shape in {"start", "end", "terminal"} else 14.0
    return (
        f'<rect x="{x:.1f}" y="{y + 4:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'rx="{radius:.1f}" fill="#0f172a" opacity="0.10"/>'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'rx="{radius:.1f}" fill="url(#node-fill)" stroke="#64748b" stroke-width="1.7"/>'
    )


def render_flowchart_svg(value: str | dict[str, Any]) -> str:
    """Render a polished vector flowchart from semantic graph data.

    This renderer is intentionally independent of the ASCII character grid: the ASCII
    diagram and the image are sibling outputs from the same graph, never screenshots of
    one another.
    """
    nodes, edges, direction = normalize_flow_spec(value)
    boxes, width, height, layers = _vector_layout(nodes, edges, direction)
    ports = _vector_ports(boxes, edges, layers, direction)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{math.ceil(width)}" height="{math.ceil(height)}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}" role="img" aria-label="Flowchart">',
        "<defs>",
        '<linearGradient id="node-fill" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffffff"/><stop offset="100%" stop-color="#f1f5f9"/>'
        "</linearGradient>",
        '<marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L9,4.5 L0,9 z" fill="#475569"/></marker>',
        "</defs>",
        '<rect width="100%" height="100%" rx="18" fill="#f8fafc"/>',
    ]

    for index, edge in enumerate(edges):
        start, end = ports[index]
        points = _vector_edge_points(index, edge, start, end, boxes, layers, width, height, direction)
        parts.append(
            f'<path d="{_svg_path(points)}" fill="none" stroke="#475569" stroke-width="2.15" '
            'stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arrow)"/>'
        )
        if edge.label:
            x, y = points[len(points) // 2]
            label = edge.label[:40]
            pill_width = max(42.0, 18.0 + len(label) * 7.2)
            parts.append(
                f'<rect x="{x - pill_width / 2:.1f}" y="{y - 15:.1f}" width="{pill_width:.1f}" '
                'height="23" rx="11.5" fill="#ffffff" stroke="#cbd5e1"/>'
            )
            parts.append(_svg_text(x, y + 1.0, label, size=11, fill="#475569", weight=600))

    for box in boxes.values():
        parts.append(_svg_flow_node(box))
        if box.node.shape not in {"decision", "diamond"}:
            parts.append(
                f'<rect x="{box.x + 14:.1f}" y="{box.y + 11:.1f}" width="32" height="4" '
                'rx="2" fill="#3b82f6" opacity="0.85"/>'
            )
        lines = _wrapped_label(box.node.label, max_width=27)
        line_height = 18.0
        start_y = box.y + box.height / 2 - ((len(lines) - 1) * line_height) / 2 + 5.0
        for index, line in enumerate(lines):
            parts.append(_svg_text(
                box.x + box.width / 2,
                start_y + index * line_height,
                line,
                size=13,
                fill="#0f172a",
                weight=650,
            ))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _ascidia_svg(ascii_text: str) -> str:
    """Parse existing ASCII through Ascidia into graphical primitives."""
    try:
        import ascidia as asc  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Ascidia is not installed. Existing ASCII-only diagrams require the optional "
            "diagram dependency (ascidia/PyCairo), or semantic nodes+edges so ComfyUI-Pi "
            "can render the native polished flowchart."
        ) from exc

    diagram = asc.process_diagram(str(ascii_text or "").replace("\t", "    "))
    stream = io.StringIO()
    prefs = asc.OutputPrefs(
        fgcolour=asc.NAMED_COLOURS.get("black", (0, 0, 0)),
        bgcolour=asc.NAMED_COLOURS.get("white", (1, 1, 1)),
        charheight=22,
    )
    asc.SvgOutput.output(diagram, stream, prefs)
    svg = stream.getvalue()
    if "<svg" not in svg:
        raise RuntimeError("Ascidia did not produce an SVG document.")
    return svg


def render_ascii_text_svg(ascii_text: str) -> str:
    """Compatibility API for hand-authored ASCII.

    There is deliberately no glyph-tracing fallback. If semantic graph data is unavailable,
    Ascidia must parse the ASCII into shapes; otherwise ComfyUI-Pi reports the missing
    capability rather than creating a screenshot-like SVG.
    """
    return _ascidia_svg(ascii_text)


def _backup_markdown(path: Path, asset_dir: Path) -> str:
    if not path.is_file():
        return ""
    backup_dir = asset_dir / "_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"{path.stem}-{stamp}-{time.time_ns() % 1_000_000:06d}{path.suffix or '.md'}"
    shutil.copy2(path, backup)
    return str(backup)


def _upsert_markdown_block(path: Path, key: str, block: str, asset_dir: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding="utf-8") if path.is_file() else ""
    backup = _backup_markdown(path, asset_dir) if original else ""
    start = f"<!-- comfyui-pi:{key}:start -->"
    end = f"<!-- comfyui-pi:{key}:end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    marker = f"<!-- comfyui-pi-insert:{key} -->"

    if start in original and end in original:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        updated = pattern.sub(wrapped, original, count=1)
    elif marker in original:
        updated = original.replace(marker, wrapped, 1)
    else:
        separator = "\n\n" if original.strip() else ""
        updated = original.rstrip() + separator + wrapped + "\n"

    atomic_write_text(path, updated)
    return backup


def create_flowchart_markdown(
    markdown_path: str,
    spec: str | dict[str, Any] | None = None,
    diagram_id: str = "flowchart",
    alt_text: str = "Flowchart",
    include_ascii: bool = True,
    ascii_text: str = "",
) -> dict[str, Any]:
    path = Path(markdown_path).expanduser().resolve()
    key = _safe_slug(diagram_id, "flowchart")
    asset_dir = path.parent / f"{path.stem}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    svg_path = asset_dir / f"{key}.svg"

    semantic = _load_json_value(spec or {})
    has_semantic_nodes = isinstance(semantic.get("nodes"), list) and bool(semantic.get("nodes"))
    supplied_ascii = str(ascii_text or "").strip("\n")

    if has_semantic_nodes:
        # One graph -> two independent renderers. Supplied model spacing is intentionally
        # ignored when semantic data exists so both outputs remain deterministic.
        rendered_ascii = render_flowchart_ascii(semantic)
        svg = render_flowchart_svg(semantic)
        renderer = "comfyui-pi-semantic-vector-svg"
        image_source = "semantic-graph"
        ascii_source = "semantic-graph"
    elif supplied_ascii:
        # Hand-authored ASCII is preserved, but the image is produced by Ascidia's pattern
        # recognizer as actual graphical primitives—not by tracing character cells.
        rendered_ascii = supplied_ascii + "\n"
        svg = render_ascii_text_svg(rendered_ascii)
        renderer = "ascidia-pattern-svg"
        image_source = "ascidia-parsed-ascii"
        ascii_source = "user-ascii"
    else:
        raise ValueError("Flowchart requires semantic nodes+edges or existing ASCII input.")

    atomic_write_text(svg_path, svg)
    rel = Path(svg_path).relative_to(path.parent).as_posix()
    blocks: list[str] = []
    if include_ascii:
        blocks.extend(["```text", rendered_ascii.rstrip(), "```", ""])
    blocks.append(f"![{str(alt_text or 'Flowchart').replace(']', '')}]({rel})")
    backup = _upsert_markdown_block(path, f"diagram:{key}", "\n".join(blocks), asset_dir)
    return {
        "ok": True,
        "markdown_path": str(path),
        "image_path": str(svg_path),
        "image_relative_path": rel,
        "ascii": rendered_ascii,
        "backup_path": backup,
        "renderer": renderer,
        "image_source": image_source,
        "ascii_source": ascii_source,
        "references": [
            "PHART hierarchical/layered ordering, distinct ports, orthogonal routing",
            "Ascidia ASCII pattern-to-graphics conversion",
        ],
    }


def _fetch_live_object_info(base_url: str, node_type: str) -> dict[str, Any]:
    base = str(base_url or "").rstrip("/")
    if not base:
        raise ValueError("Current ComfyUI base URL is required for a live v2 node image.")
    url = f"{base}/object_info/{urllib.parse.quote(str(node_type), safe='')}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    info = payload.get(node_type) if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        raise ValueError(f"Node '{node_type}' is not available in the current ComfyUI instance.")
    return info


def _find_ui_node(workflow: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    nodes = workflow.get("nodes") if isinstance(workflow.get("nodes"), list) else []
    for node in nodes:
        if isinstance(node, dict) and str(node.get("id")) == str(node_id):
            return node
    return None


def _input_schema_rows(info: dict[str, Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
    connectable: list[tuple[str, str]] = []
    widgets: list[tuple[str, str, str]] = []
    raw_input = info.get("input") if isinstance(info.get("input"), dict) else {}
    for group in ("required", "optional"):
        values = raw_input.get(group)
        if not isinstance(values, dict):
            continue
        for name, spec in values.items():
            first: Any = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
            if isinstance(first, list):
                preview = str(first[0]) if first else ""
                widgets.append((str(name), "COMBO", preview))
            else:
                dtype = str(first or "")
                if dtype in {"INT", "FLOAT", "STRING", "BOOLEAN"}:
                    widgets.append((str(name), dtype, ""))
                else:
                    connectable.append((str(name), dtype or "*"))
    return connectable, widgets


def _socket_color(dtype: str) -> str:
    key = str(dtype or "").upper()
    colors = {
        "IMAGE": "#64b5f6",
        "MASK": "#81c784",
        "LATENT": "#ba68c8",
        "CONDITIONING": "#ffb74d",
        "MODEL": "#b39ddb",
        "CLIP": "#ffd54f",
        "VAE": "#f48fb1",
        "AUDIO": "#4dd0e1",
        "STRING": "#aed581",
        "INT": "#90caf9",
        "FLOAT": "#80cbc4",
        "BOOLEAN": "#ef9a9a",
    }
    return colors.get(key, "#a0a0a0")


def render_comfyui_v2_node_svg(
    node_type: str,
    object_info: dict[str, Any],
    node: dict[str, Any] | None = None,
) -> str:
    raise RuntimeError(
        "Synthetic ComfyUI node rendering has been retired. "
        "Use comfyui_markdown_node_image so the running ComfyUI frontend renders the real installed node."
    )
    node = node or {}
    title = str(node.get("title") or object_info.get("display_name") or node_type)
    live_inputs, widget_defs = _input_schema_rows(object_info)
    serialized_inputs = node.get("inputs") if isinstance(node.get("inputs"), list) else []
    serialized_outputs = node.get("outputs") if isinstance(node.get("outputs"), list) else []

    # For an actual workflow node, preserve the exact visible link/socket names and types.
    input_rows: list[tuple[str, str]] = []
    if serialized_inputs:
        for item in serialized_inputs:
            if isinstance(item, dict):
                input_rows.append((str(item.get("name") or "input"), str(item.get("type") or "*")))
    else:
        input_rows = live_inputs

    output_rows: list[tuple[str, str]] = []
    if serialized_outputs:
        for item in serialized_outputs:
            if isinstance(item, dict):
                output_rows.append((str(item.get("name") or item.get("type") or "output"), str(item.get("type") or "*")))
    else:
        output_types = object_info.get("output") if isinstance(object_info.get("output"), list) else []
        output_names = object_info.get("output_name") if isinstance(object_info.get("output_name"), list) else []
        for index, dtype in enumerate(output_types):
            name = str(output_names[index]) if index < len(output_names) and output_names[index] else str(dtype)
            output_rows.append((name, str(dtype)))

    values = node.get("widgets_values") if isinstance(node.get("widgets_values"), list) else []
    widgets: list[tuple[str, str]] = []
    for index, (name, dtype, preview) in enumerate(widget_defs):
        value = values[index] if index < len(values) else preview
        text = str(value)
        if len(text) > 30:
            text = text[:27] + "..."
        widgets.append((name, text))

    raw_size = node.get("size")
    width = 340
    try:
        if isinstance(raw_size, (list, tuple)) and raw_size:
            width = max(280, min(520, int(float(raw_size[0]))))
        elif isinstance(raw_size, dict):
            candidate = raw_size.get(0, raw_size.get("0", raw_size.get("width")))
            if candidate is not None:
                width = max(280, min(520, int(float(candidate))))
    except Exception:
        pass

    header_h = 38
    slot_h = 24
    widget_h = 32
    slot_rows = max(1, len(input_rows), len(output_rows))
    body_h = 14 + slot_rows * slot_h + (len(widgets) * widget_h if widgets else 0) + 16
    footer_h = 12
    height = header_h + body_h + footer_h
    c = COMFY_V2_DARK

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 28}" height="{height + 20}" '
        f'viewBox="-14 -10 {width + 28} {height + 20}">',
        '<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#000000" flood-opacity="0.35"/>'
        '</filter></defs>',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="12" '
        f'fill="{c["background"]}" stroke="{c["border"]}" stroke-width="1.5" filter="url(#shadow)"/>',
        f'<path d="M12 0 H{width-12} Q{width} 0 {width} 12 V{header_h} H0 V12 Q0 0 12 0 Z" fill="{c["header"]}"/>',
        f'<line x1="0" y1="{header_h}" x2="{width}" y2="{header_h}" stroke="{c["divider"]}" stroke-width="1"/>',
        f'<polyline points="12,15 17,20 22,15" fill="none" stroke="{c["muted"]}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
        f'<text x="30" y="24" font-family="Inter,Arial,sans-serif" font-size="14" font-weight="600" '
        f'fill="{c["text"]}">{html.escape(title)}</text>',
    ]

    y0 = header_h + 18
    for row in range(slot_rows):
        y = y0 + row * slot_h
        if row < len(input_rows):
            name, dtype = input_rows[row]
            color = _socket_color(dtype)
            parts.append(f'<circle cx="0" cy="{y}" r="6" fill="{color}" stroke="{c["outline"]}" stroke-width="1.5"/>')
            parts.append(
                f'<text x="13" y="{y+4}" text-anchor="start" font-family="Inter,Arial,sans-serif" '
                f'font-size="12" fill="{c["muted"]}">{html.escape(name)}</text>'
            )
        if row < len(output_rows):
            name, dtype = output_rows[row]
            color = _socket_color(dtype)
            parts.append(f'<circle cx="{width}" cy="{y}" r="6" fill="{color}" stroke="{c["outline"]}" stroke-width="1.5"/>')
            parts.append(
                f'<text x="{width-13}" y="{y+4}" text-anchor="end" font-family="Inter,Arial,sans-serif" '
                f'font-size="12" fill="{c["muted"]}">{html.escape(name)}</text>'
            )

    widget_y = y0 + slot_rows * slot_h + 4
    for name, value in widgets:
        parts.append(
            f'<text x="12" y="{widget_y+18}" font-family="Inter,Arial,sans-serif" font-size="11" '
            f'fill="{c["muted"]}">{html.escape(name)}</text>'
        )
        field_x = min(112, max(82, width // 3))
        field_w = width - field_x - 12
        parts.append(
            f'<rect x="{field_x}" y="{widget_y+3}" width="{field_w}" height="24" rx="6" '
            f'fill="{c["widget"]}" stroke="{c["border"]}" stroke-width="0.8"/>'
        )
        parts.append(
            f'<text x="{field_x+8}" y="{widget_y+19}" font-family="Inter,Arial,sans-serif" '
            f'font-size="11" fill="{c["text"]}">{html.escape(value)}</text>'
        )
        widget_y += widget_h

    footer_y = height - footer_h
    parts.append(f'<line x1="0" y1="{footer_y}" x2="{width}" y2="{footer_y}" stroke="{c["divider"]}" stroke-width="1"/>')
    parts.append(
        f'<path d="M{width-10} {height-4} L{width-4} {height-10} M{width-7} {height-4} L{width-4} {height-7}" '
        f'stroke="{c["muted"]}" stroke-width="1" opacity="0.55"/>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def create_comfyui_v2_node_markdown(
    markdown_path: str,
    base_url: str,
    workflow_path: str = "",
    node_id: str = "",
    node_type: str = "",
    image_id: str = "",
    alt_text: str = "",
) -> dict[str, Any]:
    raise RuntimeError(
        "Synthetic ComfyUI node Markdown rendering has been retired. "
        "Use the comfyui_markdown_node_image Pi tool for a real Playwright capture."
    )
    markdown = Path(markdown_path).expanduser().resolve()
    node: dict[str, Any] = {}
    workflow_file = Path(workflow_path).expanduser().resolve() if workflow_path else None
    if workflow_file and workflow_file.is_file():
        workflow = _load_json_value(str(workflow_file))
        found = _find_ui_node(workflow, node_id)
        if found is None and node_id:
            raise ValueError(f"Workflow node id '{node_id}' was not found.")
        node = found or {}
        node_type = str(node.get("type") or node_type)

    node_type = str(node_type or "").strip()
    if not node_type:
        raise ValueError("A live ComfyUI node type is required.")
    info = _fetch_live_object_info(base_url, node_type)

    key = _safe_slug(image_id or f"node-{node_id or node_type}", "node")
    asset_dir = markdown.parent / f"{markdown.stem}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    svg_path = asset_dir / f"{key}.svg"
    atomic_write_text(svg_path, render_comfyui_v2_node_svg(node_type, info, node=node))

    rel = svg_path.relative_to(markdown.parent).as_posix()
    alt = str(alt_text or node.get("title") or info.get("display_name") or node_type).replace("]", "")
    block = f"![{alt}]({rel})"
    backup = _upsert_markdown_block(markdown, f"node:{key}", block, asset_dir)
    return {
        "ok": True,
        "markdown_path": str(markdown),
        "image_path": str(svg_path),
        "image_relative_path": rel,
        "backup_path": backup,
        "node_id": str(node_id or ""),
        "node_type": node_type,
        "renderer": "comfyui-v2-svg",
        "live_schema_verified": True,
    }
