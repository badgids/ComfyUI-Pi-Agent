from __future__ import annotations

import html
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
    ids = [node.id for node in nodes]
    order_index = {node_id: index for index, node_id in enumerate(ids)}
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in ids}
    for edge in edges:
        if edge.target not in adjacency[edge.source]:
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1
    for values in adjacency.values():
        values.sort(key=lambda node_id: order_index[node_id])

    queue = deque(node_id for node_id in ids if indegree[node_id] == 0)
    layers = {node_id: 0 for node_id in ids}
    visited: list[str] = []
    while queue:
        current = queue.popleft()
        visited.append(current)
        for target in adjacency[current]:
            layers[target] = max(layers[target], layers[current] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(visited) == len(ids):
        return layers

    # PHART-inspired deterministic layered fallback for cyclic/non-DAG graphs: BFS depth,
    # starting with source-like nodes, then remaining nodes in declared order.
    assigned: set[str] = set()
    roots = [node_id for node_id in ids if all(edge.target != node_id for edge in edges)] or [ids[0]]
    depth = 0
    frontier = deque((node_id, 0) for node_id in roots)
    while frontier:
        current, current_depth = frontier.popleft()
        if current in assigned:
            continue
        assigned.add(current)
        layers[current] = current_depth
        for target in adjacency[current]:
            if target not in assigned:
                frontier.append((target, current_depth + 1))
    for node_id in ids:
        if node_id not in assigned:
            depth = max(layers.values(), default=0) + 1
            layers[node_id] = depth
            assigned.add(node_id)
    return layers


def _layout(nodes: list[FlowNode], edges: list[FlowEdge], direction: str) -> tuple[dict[str, Box], int, int]:
    layers = _assign_layers(nodes, edges)
    grouped: dict[int, list[FlowNode]] = defaultdict(list)
    for node in nodes:
        grouped[layers[node.id]].append(node)

    sizes: dict[str, tuple[int, int]] = {}
    for node in nodes:
        lines = _wrapped_label(node.label)
        width = max(10, max((len(line) for line in lines), default=0) + 4)
        height = max(3, len(lines) + 2)
        sizes[node.id] = (width, height)

    boxes: dict[str, Box] = {}
    if direction == "LR":
        x = 2
        max_total_height = max(
            (sum(sizes[node.id][1] for node in layer_nodes) + max(0, len(layer_nodes) - 1) * 3
             for layer_nodes in grouped.values()),
            default=1,
        )
        for layer in sorted(grouped):
            layer_nodes = grouped[layer]
            total_height = sum(sizes[node.id][1] for node in layer_nodes) + max(0, len(layer_nodes) - 1) * 3
            y = 2 + max(0, (max_total_height - total_height) // 2)
            layer_width = max(sizes[node.id][0] for node in layer_nodes)
            for node in layer_nodes:
                width, height = sizes[node.id]
                boxes[node.id] = Box(node, x, y, width, height)
                y += height + 3
            x += layer_width + 8
        canvas_width = max((box.x + box.width for box in boxes.values()), default=0) + 3
        canvas_height = max((box.y + box.height for box in boxes.values()), default=0) + 3
    else:
        y = 2
        max_total_width = max(
            (sum(sizes[node.id][0] for node in layer_nodes) + max(0, len(layer_nodes) - 1) * 6
             for layer_nodes in grouped.values()),
            default=1,
        )
        for layer in sorted(grouped):
            layer_nodes = grouped[layer]
            total_width = sum(sizes[node.id][0] for node in layer_nodes) + max(0, len(layer_nodes) - 1) * 6
            x = 2 + max(0, (max_total_width - total_width) // 2)
            layer_height = max(sizes[node.id][1] for node in layer_nodes)
            for node in layer_nodes:
                width, height = sizes[node.id]
                boxes[node.id] = Box(node, x, y, width, height)
                x += width + 6
            y += layer_height + 5
        canvas_width = max((box.x + box.width for box in boxes.values()), default=0) + 3
        canvas_height = max((box.y + box.height for box in boxes.values()), default=0) + 3
    return boxes, canvas_width, canvas_height


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
    nodes, edges, direction = normalize_flow_spec(value)
    boxes, width, height = _layout(nodes, edges, direction)
    grid = [[" " for _ in range(max(1, width))] for _ in range(max(1, height))]
    arrows: list[tuple[int, int, str]] = []

    # Draw Manhattan connectors first; boxes overwrite line segments at their boundaries.
    for edge in edges:
        source = boxes[edge.source]
        target = boxes[edge.target]
        if direction == "LR":
            sx = source.x + source.width
            sy = source.y + source.height // 2
            tx = target.x - 1
            ty = target.y + target.height // 2
            if sy == ty:
                _line_h(grid, sx, tx, sy)
            else:
                mid_x = sx + max(1, (tx - sx) // 2)
                _line_h(grid, sx, mid_x, sy)
                _line_v(grid, mid_x, sy, ty)
                _line_h(grid, mid_x, tx, ty)
            arrows.append((tx, ty, ">"))
        else:
            sx = source.x + source.width // 2
            sy = source.y + source.height
            tx = target.x + target.width // 2
            ty = target.y - 1
            if sx == tx:
                _line_v(grid, sx, sy, ty)
            else:
                mid_y = sy + max(1, (ty - sy) // 2)
                _line_v(grid, sx, sy, mid_y)
                _line_h(grid, sx, tx, mid_y)
                _line_v(grid, tx, mid_y, ty)
            arrows.append((tx, ty, "v"))

    for box in boxes.values():
        x, y, width, height = box.x, box.y, box.width, box.height
        _put(grid, x, y, "+")
        _put(grid, x + width - 1, y, "+")
        _put(grid, x, y + height - 1, "+")
        _put(grid, x + width - 1, y + height - 1, "+")
        for xx in range(x + 1, x + width - 1):
            _put(grid, xx, y, "-")
            _put(grid, xx, y + height - 1, "-")
        for yy in range(y + 1, y + height - 1):
            _put(grid, x, yy, "|")
            _put(grid, x + width - 1, yy, "|")
        lines = _wrapped_label(box.node.label, max_width=max(1, width - 4))
        start_y = y + max(1, (height - len(lines)) // 2)
        for offset, line in enumerate(lines):
            label = line[: width - 4]
            start_x = x + max(2, (width - len(label)) // 2)
            for index, char in enumerate(label):
                if start_x + index < x + width - 1:
                    grid[start_y + offset][start_x + index] = char

    for x, y, char in arrows:
        _put(grid, x, y, char)

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
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(value)}</text>'
    )


def render_flowchart_svg(value: str | dict[str, Any]) -> str:
    nodes, edges, direction = normalize_flow_spec(value)
    boxes, char_width, char_height = _layout(nodes, edges, direction)
    sx, sy = 10.0, 18.0
    pad = 18.0
    width = char_width * sx + pad * 2
    height = char_height * sy + pad * 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{math.ceil(width)}" height="{math.ceil(height)}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" '
        'markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 z" fill="#475569"/></marker></defs>',
        '<rect width="100%" height="100%" rx="12" fill="#ffffff"/>',
    ]

    def cx(box: Box) -> float:
        return pad + (box.x + box.width / 2) * sx

    def cy(box: Box) -> float:
        return pad + (box.y + box.height / 2) * sy

    for edge in edges:
        source, target = boxes[edge.source], boxes[edge.target]
        if direction == "LR":
            x1 = pad + (source.x + source.width) * sx
            y1 = cy(source)
            x2 = pad + target.x * sx
            y2 = cy(target)
            mx = (x1 + x2) / 2
            path = f"M{x1:.1f},{y1:.1f} H{mx:.1f} V{y2:.1f} H{x2:.1f}"
            label_x, label_y = mx, min(y1, y2) - 6
        else:
            x1 = cx(source)
            y1 = pad + (source.y + source.height) * sy
            x2 = cx(target)
            y2 = pad + target.y * sy
            my = (y1 + y2) / 2
            path = f"M{x1:.1f},{y1:.1f} V{my:.1f} H{x2:.1f} V{y2:.1f}"
            label_x, label_y = (x1 + x2) / 2, my - 6
        parts.append(
            f'<path d="{path}" fill="none" stroke="#475569" stroke-width="2" '
            f'stroke-linejoin="round" marker-end="url(#arrow)"/>'
        )
        if edge.label:
            parts.append(_svg_text(label_x, label_y, edge.label[:40], size=11, fill="#475569"))

    for box in boxes.values():
        x = pad + box.x * sx
        y = pad + box.y * sy
        w = box.width * sx
        h = box.height * sy
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            'rx="10" fill="#f8fafc" stroke="#334155" stroke-width="2"/>'
        )
        lines = _wrapped_label(box.node.label, max_width=max(8, box.width - 4))
        line_height = 16
        start_y = y + h / 2 - ((len(lines) - 1) * line_height) / 2 + 5
        for idx, line in enumerate(lines):
            parts.append(_svg_text(x + w / 2, start_y + idx * line_height, line, size=13, fill="#0f172a", weight=600))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_ascii_text_svg(ascii_text: str) -> str:
    """Vectorize an ASCII diagram using Ascidia-compatible line/arrow conventions."""
    lines = str(ascii_text or "").replace("\t", "    ").splitlines() or [""]
    cell_w, cell_h = 10.0, 18.0
    pad = 18.0
    columns = max(1, max(len(line) for line in lines))
    width = columns * cell_w + pad * 2
    height = max(1, len(lines)) * cell_h + pad * 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{math.ceil(width)}" height="{math.ceil(height)}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        '<rect width="100%" height="100%" rx="10" fill="#ffffff"/>',
        '<g stroke="#334155" stroke-width="1.8" fill="none" stroke-linecap="square">',
    ]

    def center(col: int, row: int) -> tuple[float, float]:
        return pad + (col + 0.5) * cell_w, pad + (row + 0.5) * cell_h

    for row, line in enumerate(lines):
        for col, char in enumerate(line):
            x, y = center(col, row)
            left, right = x - cell_w / 2, x + cell_w / 2
            top, bottom = y - cell_h / 2, y + cell_h / 2
            if char == "-":
                parts.append(f'<path d="M{left:.1f},{y:.1f} H{right:.1f}"/>')
            elif char == "|":
                parts.append(f'<path d="M{x:.1f},{top:.1f} V{bottom:.1f}"/>')
            elif char == "+":
                parts.append(f'<path d="M{left:.1f},{y:.1f} H{right:.1f} M{x:.1f},{top:.1f} V{bottom:.1f}"/>')
            elif char == ">":
                parts.append(f'<path d="M{left:.1f},{y:.1f} H{x-2:.1f}"/>')
                parts.append(f'<path d="M{x-2:.1f},{y-4:.1f} L{x+4:.1f},{y:.1f} L{x-2:.1f},{y+4:.1f} Z" fill="#334155"/>')
            elif char == "<":
                parts.append(f'<path d="M{x+2:.1f},{y:.1f} H{right:.1f}"/>')
                parts.append(f'<path d="M{x+2:.1f},{y-4:.1f} L{x-4:.1f},{y:.1f} L{x+2:.1f},{y+4:.1f} Z" fill="#334155"/>')
            elif char in {"^", "v", "V"}:
                if char == "^":
                    points = f"{x-4:.1f},{y+2:.1f} {x:.1f},{y-4:.1f} {x+4:.1f},{y+2:.1f}"
                    parts.append(f'<path d="M{x:.1f},{y+2:.1f} V{bottom:.1f}"/>')
                else:
                    points = f"{x-4:.1f},{y-2:.1f} {x:.1f},{y+4:.1f} {x+4:.1f},{y-2:.1f}"
                    parts.append(f'<path d="M{x:.1f},{top:.1f} V{y-2:.1f}"/>')
                parts.append(f'<polygon points="{points}" fill="#334155" stroke="none"/>')
    parts.append("</g>")

    # Render non-line glyphs in stable monospaced runs so box labels remain aligned.
    for row, line in enumerate(lines):
        col = 0
        while col < len(line):
            if line[col] in "-|+><^vV ":
                col += 1
                continue
            start_col = col
            chars: list[str] = []
            while col < len(line) and line[col] not in "-|+><^vV":
                chars.append(line[col])
                col += 1
            text = "".join(chars).rstrip()
            if text:
                x = pad + start_col * cell_w
                y = pad + (row + 0.72) * cell_h
                parts.append(
                    f'<text x="{x:.1f}" y="{y:.1f}" xml:space="preserve" '
                    'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
                    f'font-size="13" fill="#0f172a">{html.escape(text)}</text>'
                )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


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

    supplied_ascii = str(ascii_text or "").strip("\n")
    if supplied_ascii:
        rendered_ascii = supplied_ascii + "\n"
        svg = render_ascii_text_svg(rendered_ascii)
        renderer = "comfyui-pi-ascii-vector-svg"
    else:
        rendered_ascii = render_flowchart_ascii(spec or {})
        svg = render_flowchart_svg(spec or {})
        renderer = "comfyui-pi-hierarchical-orthogonal-svg"
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
        "references": ["PHART layout concepts", "Ascidia ASCII diagram conventions"],
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
