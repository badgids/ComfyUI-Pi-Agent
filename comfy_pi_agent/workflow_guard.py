from __future__ import annotations

import copy
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any

from .compat import get_live_node_registry
from .io_utils import load_json

MIN_NODE_GAP = 6.0
V2_RENDERER = "Vue-corrected"
FRONTEND_NODE_TYPES = {"Reroute", "Note"}


@dataclass
class WorkflowGateIssue:
    severity: str
    code: str
    message: str
    node_id: str | None = None
    link_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_format(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("nodes"), list):
        return "ui"
    if isinstance(data, dict) and data and all(isinstance(value, dict) for value in data.values()):
        if any("class_type" in value for value in data.values()):
            return "api"
    return "unknown"


def _node_id(value: Any) -> str:
    return str(value)


def _pair(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return default
    if isinstance(value, dict):
        try:
            return float(value.get(0, value.get("0"))), float(value.get(1, value.get("1")))
        except (TypeError, ValueError):
            return default
    return default


def _type_tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        result: set[str] = set()
        for item in value:
            result.update(_type_tokens(item))
        return result
    text = str(value).strip()
    if not text:
        return set()
    if text in {"*", "ANY", "any"}:
        return {"*"}
    return {part.strip() for part in text.split(",") if part.strip()}


def _types_compatible(*values: Any) -> bool:
    groups = [tokens for tokens in (_type_tokens(value) for value in values) if tokens]
    if len(groups) <= 1 or any("*" in tokens for tokens in groups):
        return True
    common = set(groups[0])
    for tokens in groups[1:]:
        common.intersection_update(tokens)
    return bool(common)


def _input_type(spec: Any) -> Any:
    first = spec[0] if isinstance(spec, (tuple, list)) and spec else spec
    # ComfyUI combo/widget inputs use a literal option list, not a connectable datatype.
    if isinstance(first, (list, tuple)) and not isinstance(first, str):
        return None
    return first if isinstance(first, (str, int, float)) else None


def _schema_for(node_class: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    required: set[str] = set()
    optional: set[str] = set()
    hidden: set[str] = set()
    try:
        fn = getattr(node_class, "INPUT_TYPES", None)
        raw = fn() if callable(fn) else {}
        if isinstance(raw, dict):
            for group_name, names in raw.items():
                if not isinstance(names, dict):
                    continue
                for name, spec in names.items():
                    name = str(name)
                    inputs[name] = _input_type(spec)
                    if group_name == "required":
                        required.add(name)
                    elif group_name == "optional":
                        optional.add(name)
                    elif group_name == "hidden":
                        hidden.add(name)
    except Exception:
        pass

    outputs: list[Any] = []
    try:
        raw_outputs = getattr(node_class, "RETURN_TYPES", ())
        if isinstance(raw_outputs, (list, tuple)):
            outputs = list(raw_outputs)
    except Exception:
        pass

    # ComfyUI currently adapts V3/ComfyExtension nodes into the live registry used by
    # /object_info. Keep a conservative fallback for runtimes exposing define_schema.
    if not inputs and not outputs:
        try:
            fn = getattr(node_class, "define_schema", None)
            schema = fn() if callable(fn) else None
            for item in list(getattr(schema, "inputs", []) or []):
                name = str(getattr(item, "name", "") or "")
                if not name:
                    continue
                dtype = getattr(item, "type", None)
                if dtype is None:
                    dtype = getattr(item, "io_type", None)
                inputs[name] = str(dtype) if dtype is not None else None
                (optional if bool(getattr(item, "optional", False)) else required).add(name)
            for item in list(getattr(schema, "outputs", []) or []):
                dtype = getattr(item, "type", None)
                if dtype is None:
                    dtype = getattr(item, "io_type", None)
                outputs.append(str(dtype) if dtype is not None else None)
        except Exception:
            pass

    return {
        "inputs": inputs,
        "required": required,
        "optional": optional,
        "hidden": hidden,
        "outputs": outputs,
        "output_node": bool(getattr(node_class, "OUTPUT_NODE", False)),
    }


def live_node_catalog(live_registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = live_registry if live_registry is not None else get_live_node_registry()
    return {
        "available": bool(registry),
        "node_count": len(registry),
        "node_types": sorted(str(name) for name in registry),
        "frontend_node_types": sorted(FRONTEND_NODE_TYPES),
        "nodes_v2": True,
        "workflow_renderer": V2_RENDERER,
        "minimum_node_gap_px": MIN_NODE_GAP,
    }


def _iter_ui_links(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    raw_links = workflow.get("links")
    if not isinstance(raw_links, list):
        return result
    for raw in raw_links:
        if isinstance(raw, list) and len(raw) >= 6:
            result.append({
                "id": raw[0], "source": raw[1], "source_slot": raw[2],
                "target": raw[3], "target_slot": raw[4], "type": raw[5],
            })
        elif isinstance(raw, dict):
            result.append({
                "id": raw.get("id"), "source": raw.get("origin_id"),
                "source_slot": raw.get("origin_slot"), "target": raw.get("target_id"),
                "target_slot": raw.get("target_slot"), "type": raw.get("type"),
            })
    return result


def _topology_ui(workflow: dict[str, Any]) -> tuple[list[str], dict[str, int], bool]:
    nodes = [node for node in workflow.get("nodes", []) if isinstance(node, dict)]
    ids = {_node_id(node.get("id")) for node in nodes}
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {node_id: 0 for node_id in ids}
    for link in _iter_ui_links(workflow):
        source, target = _node_id(link["source"]), _node_id(link["target"])
        if source not in ids or target not in ids or target in adjacency[source]:
            continue
        adjacency[source].add(target)
        indegree[target] += 1

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    order: list[str] = []
    layers: dict[str, int] = {node_id: 0 for node_id in ids}
    while queue:
        current = queue.popleft()
        order.append(current)
        for target in sorted(adjacency[current]):
            layers[target] = max(layers[target], layers[current] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    cycle = len(order) != len(ids)
    if cycle:
        layer = max(layers.values(), default=0) + 1
        for node_id in sorted(ids.difference(order)):
            order.append(node_id)
            layers[node_id] = layer
            layer += 1
    return order, layers, cycle


def organize_ui_workflow(
    value: str | dict[str, Any],
    minimum_gap: float = MIN_NODE_GAP,
    horizontal_gap: float = 80.0,
    vertical_gap: float = 36.0,
) -> dict[str, Any]:
    data = load_json(value, default={})
    if _detect_format(data) != "ui":
        return copy.deepcopy(data) if isinstance(data, dict) else {}

    workflow = copy.deepcopy(data)
    nodes = [node for node in workflow.get("nodes", []) if isinstance(node, dict)]
    _, layer_by_id, _ = _topology_ui(workflow)
    columns: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for node in nodes:
        width, height = _pair(node.get("size"), (320.0, 180.0))
        node["size"] = [max(40.0, width), max(24.0, height)]
        columns[layer_by_id.get(_node_id(node.get("id")), 0)].append(node)

    x = 0.0
    h_gap = max(float(minimum_gap), float(horizontal_gap))
    v_gap = max(float(minimum_gap), float(vertical_gap))
    for layer in sorted(columns):
        column = columns[layer]
        column.sort(key=lambda node: (_pair(node.get("pos"), (0.0, 0.0))[1], _node_id(node.get("id"))))
        max_width = max((_pair(node.get("size"), (320.0, 180.0))[0] for node in column), default=320.0)
        y = 0.0
        for node in column:
            _, height = _pair(node.get("size"), (320.0, 180.0))
            node["pos"] = [x, y]
            y += height + v_gap
        x += max_width + h_gap

    extra = workflow.get("extra")
    if not isinstance(extra, dict):
        extra = {}
        workflow["extra"] = extra
    extra["workflowRendererVersion"] = V2_RENDERER

    metadata = extra.get("comfyui_pi_agent")
    if not isinstance(metadata, dict):
        metadata = {}
        extra["comfyui_pi_agent"] = metadata
    metadata["workflow_contract"] = {
        "nodes_v2": True,
        "renderer": V2_RENDERER,
        "minimum_node_gap_px": float(minimum_gap),
        "layout": "deterministic-left-to-right",
    }
    return workflow


def _validate_layout(nodes: list[dict[str, Any]], minimum_gap: float, issues: list[WorkflowGateIssue]) -> None:
    boxes: list[tuple[str, float, float, float, float]] = []
    for node in nodes:
        node_id = _node_id(node.get("id"))
        x, y = _pair(node.get("pos"), (float("nan"), float("nan")))
        width, height = _pair(node.get("size"), (float("nan"), float("nan")))
        if not all(value == value for value in (x, y, width, height)) or width <= 0 or height <= 0:
            issues.append(WorkflowGateIssue(
                "error", "invalid_node_geometry",
                "Node requires finite pos and positive size for Nodes 2.0 layout.", node_id,
            ))
            continue
        boxes.append((node_id, x, y, width, height))

    gap = float(minimum_gap)
    for index, (a_id, ax, ay, aw, ah) in enumerate(boxes):
        for b_id, bx, by, bw, bh in boxes[index + 1:]:
            separated = (
                ax + aw + gap <= bx or bx + bw + gap <= ax
                or ay + ah + gap <= by or by + bh + gap <= ay
            )
            if not separated:
                issues.append(WorkflowGateIssue(
                    "error", "node_gap_violation",
                    f"Nodes {a_id} and {b_id} overlap or are closer than {gap:g}px.", a_id,
                ))


def _validate_ui(
    workflow: dict[str, Any],
    registry: dict[str, Any],
    minimum_gap: float,
    issues: list[WorkflowGateIssue],
) -> tuple[bool, bool]:
    nodes = [node for node in workflow.get("nodes", []) if isinstance(node, dict)]
    node_by_id = {_node_id(node.get("id")): node for node in nodes}
    schema_by_id: dict[str, dict[str, Any]] = {}
    has_output = False

    for node_id, node in node_by_id.items():
        node_type = str(node.get("type") or "")
        if not node_type:
            issues.append(WorkflowGateIssue("error", "missing_node_type", "Node has no type.", node_id))
            continue
        if node_type in FRONTEND_NODE_TYPES:
            continue
        node_class = registry.get(node_type)
        if node_class is None:
            issues.append(WorkflowGateIssue(
                "error", "missing_live_node",
                f"Node '{node_type}' is not registered in the current ComfyUI instance.", node_id,
            ))
            continue
        schema = _schema_for(node_class)
        schema_by_id[node_id] = schema
        has_output = has_output or schema["output_node"]

    link_ids: set[str] = set()
    target_slots: set[tuple[str, int]] = set()
    for link in _iter_ui_links(workflow):
        link_id = _node_id(link.get("id"))
        link_ids.add(link_id)
        source_id, target_id = _node_id(link.get("source")), _node_id(link.get("target"))
        try:
            source_slot, target_slot = int(link.get("source_slot")), int(link.get("target_slot"))
        except (TypeError, ValueError):
            issues.append(WorkflowGateIssue("error", "invalid_link_slot", "Link slots must be integer indexes.", link_id=link_id))
            continue

        source, target = node_by_id.get(source_id), node_by_id.get(target_id)
        if source is None or target is None:
            issues.append(WorkflowGateIssue("error", "dangling_link", f"Link {link_id} references a missing node.", link_id=link_id))
            continue

        target_key = (target_id, target_slot)
        if target_key in target_slots:
            issues.append(WorkflowGateIssue("error", "multiple_links_to_input", f"More than one link targets node {target_id} input slot {target_slot}.", target_id, link_id))
        target_slots.add(target_key)

        outputs = source.get("outputs") if isinstance(source.get("outputs"), list) else []
        inputs = target.get("inputs") if isinstance(target.get("inputs"), list) else []
        if not 0 <= source_slot < len(outputs):
            issues.append(WorkflowGateIssue("error", "source_slot_out_of_range", f"Source slot {source_slot} does not exist on node {source_id}.", source_id, link_id))
            continue
        if not 0 <= target_slot < len(inputs):
            issues.append(WorkflowGateIssue("error", "target_slot_out_of_range", f"Target slot {target_slot} does not exist on node {target_id}.", target_id, link_id))
            continue

        source_output = outputs[source_slot] if isinstance(outputs[source_slot], dict) else {}
        target_input = inputs[target_slot] if isinstance(inputs[target_slot], dict) else {}
        source_type, target_type, link_type = source_output.get("type"), target_input.get("type"), link.get("type")
        if not _types_compatible(source_type, target_type, link_type):
            issues.append(WorkflowGateIssue("error", "serialized_type_mismatch", f"Link {link_id} has incompatible serialized datatypes.", target_id, link_id))

        if isinstance(source_output.get("links"), list) and link_id not in {_node_id(item) for item in source_output["links"]}:
            issues.append(WorkflowGateIssue("error", "source_link_backref_missing", f"Source node {source_id} does not reference link {link_id}.", source_id, link_id))
        if target_input.get("link") is not None and _node_id(target_input.get("link")) != link_id:
            issues.append(WorkflowGateIssue("error", "target_link_backref_mismatch", f"Target node {target_id} does not reference link {link_id}.", target_id, link_id))

        source_schema = schema_by_id.get(source_id)
        if source_schema is not None:
            live_outputs = source_schema["outputs"]
            if source_slot >= len(live_outputs):
                issues.append(WorkflowGateIssue("error", "live_source_slot_missing", f"Live schema for node {source_id} has no output slot {source_slot}.", source_id, link_id))
            elif not _types_compatible(live_outputs[source_slot], source_type, link_type):
                issues.append(WorkflowGateIssue("error", "live_source_type_mismatch", f"Link {link_id} disagrees with node {source_id}'s live output type.", source_id, link_id))

        target_schema = schema_by_id.get(target_id)
        if target_schema is not None:
            input_name = str(target_input.get("name") or "")
            if input_name not in target_schema["inputs"]:
                issues.append(WorkflowGateIssue("error", "live_target_input_missing", f"Live schema for node {target_id} has no input '{input_name}'.", target_id, link_id))
            else:
                live_type = target_schema["inputs"][input_name]
                if live_type is None:
                    issues.append(WorkflowGateIssue("error", "linked_widget_input", f"Node {target_id}.{input_name} is not a connectable datatype.", target_id, link_id))
                elif not _types_compatible(live_type, target_type, link_type):
                    issues.append(WorkflowGateIssue("error", "live_target_type_mismatch", f"Link {link_id} disagrees with node {target_id}.{input_name}'s live datatype.", target_id, link_id))

    for node_id, node in node_by_id.items():
        for slot in node.get("inputs") if isinstance(node.get("inputs"), list) else []:
            if isinstance(slot, dict) and slot.get("link") is not None and _node_id(slot["link"]) not in link_ids:
                issues.append(WorkflowGateIssue("error", "orphan_input_link", f"Node {node_id} references missing input link {slot['link']}.", node_id))
        for slot in node.get("outputs") if isinstance(node.get("outputs"), list) else []:
            if not isinstance(slot, dict):
                continue
            for item in slot.get("links") if isinstance(slot.get("links"), list) else []:
                if _node_id(item) not in link_ids:
                    issues.append(WorkflowGateIssue("error", "orphan_output_link", f"Node {node_id} references missing output link {item}.", node_id))

    _, _, cycle = _topology_ui(workflow)
    if cycle:
        issues.append(WorkflowGateIssue("error", "cycle_detected", "Generated execution graph contains a cycle."))

    _validate_layout(nodes, minimum_gap, issues)
    extra = workflow.get("extra") if isinstance(workflow.get("extra"), dict) else {}
    nodes_v2 = str(extra.get("workflowRendererVersion") or "") == V2_RENDERER
    if not nodes_v2:
        issues.append(WorkflowGateIssue("error", "nodes_v2_required", f"Generated UI workflows must use Nodes 2.0 renderer '{V2_RENDERER}'."))

    if not has_output:
        issues.append(WorkflowGateIssue("error", "no_output_node", "Workflow has no real live ComfyUI OUTPUT_NODE."))
    return has_output, nodes_v2


def _validate_api(workflow: dict[str, Any], registry: dict[str, Any], issues: list[WorkflowGateIssue]) -> bool:
    nodes = {str(node_id): node for node_id, node in workflow.items() if isinstance(node, dict)}
    schemas: dict[str, dict[str, Any]] = {}
    has_output = False

    for node_id, node in nodes.items():
        node_type = str(node.get("class_type") or "")
        node_class = registry.get(node_type)
        if not node_type or node_class is None:
            issues.append(WorkflowGateIssue("error", "missing_live_node", f"Node '{node_type or '<missing>'}' is not registered in the current ComfyUI instance.", node_id))
            continue
        schema = _schema_for(node_class)
        schemas[node_id] = schema
        has_output = has_output or schema["output_node"]
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            issues.append(WorkflowGateIssue("error", "invalid_inputs", "API node inputs must be an object.", node_id))
            continue
        for required_name in schema["required"]:
            if required_name not in inputs:
                issues.append(WorkflowGateIssue("error", "missing_required_input", f"Required live input '{required_name}' is missing from node {node_id}.", node_id))

    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {node_id: 0 for node_id in nodes}
    for target_id, node in nodes.items():
        target_schema = schemas.get(target_id)
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        for input_name, value in inputs.items():
            if not (isinstance(value, list) and len(value) >= 2 and str(value[0]) in nodes):
                continue
            source_id = str(value[0])
            try:
                source_slot = int(value[1])
            except (TypeError, ValueError):
                issues.append(WorkflowGateIssue("error", "invalid_link_slot", f"API link into {target_id}.{input_name} has a non-integer source slot.", target_id))
                continue
            source_schema = schemas.get(source_id)
            if source_schema is None:
                continue
            outputs = source_schema["outputs"]
            if not 0 <= source_slot < len(outputs):
                issues.append(WorkflowGateIssue("error", "live_source_slot_missing", f"Node {source_id} has no live output slot {source_slot}.", source_id))
                continue
            if target_schema is None or input_name not in target_schema["inputs"]:
                issues.append(WorkflowGateIssue("error", "live_target_input_missing", f"Node {target_id} has no live input '{input_name}'.", target_id))
                continue
            expected = target_schema["inputs"][input_name]
            if expected is None:
                issues.append(WorkflowGateIssue("error", "linked_widget_input", f"Node {target_id}.{input_name} is not a connectable datatype.", target_id))
            elif not _types_compatible(outputs[source_slot], expected):
                issues.append(WorkflowGateIssue("error", "live_connection_type_mismatch", f"Connection {source_id}[{source_slot}] -> {target_id}.{input_name} has incompatible live datatypes.", target_id))
            if target_id not in adjacency[source_id]:
                adjacency[source_id].add(target_id)
                indegree[target_id] += 1

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        issues.append(WorkflowGateIssue("error", "cycle_detected", "API execution graph contains a cycle."))
    if not has_output:
        issues.append(WorkflowGateIssue("error", "no_output_node", "API graph has no real live ComfyUI OUTPUT_NODE."))
    return has_output


def validate_generated_workflow(
    value: str | dict[str, Any],
    live_registry: dict[str, Any] | None = None,
    minimum_gap: float = MIN_NODE_GAP,
) -> dict[str, Any]:
    workflow = load_json(value, default={})
    fmt = _detect_format(workflow)
    registry = live_registry if live_registry is not None else get_live_node_registry()
    issues: list[WorkflowGateIssue] = []

    if not registry:
        issues.append(WorkflowGateIssue(
            "error", "live_registry_unavailable",
            "The current ComfyUI live node registry is unavailable. Generated-workflow completion cannot be verified.",
        ))

    has_output = False
    nodes_v2 = fmt != "ui"
    if fmt == "ui":
        has_output, nodes_v2 = _validate_ui(workflow, registry, max(MIN_NODE_GAP, float(minimum_gap)), issues)
    elif fmt == "api":
        has_output = _validate_api(workflow, registry, issues)
    else:
        issues.append(WorkflowGateIssue("error", "unknown_format", "Workflow is not a recognized ComfyUI UI workflow or API prompt graph."))

    errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
    warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
    return {
        "format": fmt,
        "valid": not errors,
        "live_registry_available": bool(registry),
        "live_node_count": len(registry),
        "nodes_v2": bool(nodes_v2),
        "workflow_renderer": V2_RENDERER if fmt == "ui" else "not-applicable-api-prompt",
        "minimum_node_gap_px": max(MIN_NODE_GAP, float(minimum_gap)),
        "has_output_node": has_output,
        "issues": errors + warnings,
    }


def finalize_generated_workflow(
    value: str | dict[str, Any],
    live_registry: dict[str, Any] | None = None,
    minimum_gap: float = MIN_NODE_GAP,
    organize: bool = True,
) -> dict[str, Any]:
    workflow = load_json(value, default={})
    fmt = _detect_format(workflow)
    if fmt == "ui":
        finalized = organize_ui_workflow(workflow, max(MIN_NODE_GAP, float(minimum_gap))) if organize else copy.deepcopy(workflow)
        if not organize:
            extra = finalized.get("extra")
            if not isinstance(extra, dict):
                extra = {}
                finalized["extra"] = extra
            extra["workflowRendererVersion"] = V2_RENDERER
    else:
        finalized = copy.deepcopy(workflow) if isinstance(workflow, dict) else {}

    validation = validate_generated_workflow(finalized, live_registry=live_registry, minimum_gap=minimum_gap)
    return {
        **validation,
        "workflow": finalized,
        "runnable_candidate": bool(validation["valid"] and validation["has_output_node"]),
        "completion_verified": False,
        "native_validation": {
            "attempted": False,
            "valid": False,
            "reason": "Native ComfyUI execution.validate_prompt has not run yet.",
        },
    }


def finalize_workflow_result(result: dict[str, Any]) -> dict[str, Any]:
    """Strictly gate built-in ComfyUI-Pi workflow-generator results."""
    if not isinstance(result, dict) or not isinstance(result.get("workflow"), dict):
        return result
    finalized = finalize_generated_workflow(result["workflow"])
    output = dict(result)
    output["workflow"] = finalized["workflow"]
    output["workflow_gate"] = {key: value for key, value in finalized.items() if key != "workflow"}
    if finalized["live_registry_available"]:
        output["ok"] = bool(output.get("ok", True) and finalized["valid"])
        if not finalized["valid"] and not output.get("error"):
            output["error"] = "Generated workflow failed the current-instance live node/socket/layout/output gate."
    output["runnable"] = bool(output.get("runnable", False) and finalized["runnable_candidate"] and finalized["completion_verified"])
    return output
