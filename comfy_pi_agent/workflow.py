from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .compat import get_live_node_registry
from .io_utils import load_json
from .integrations.router import match_integrations, load_integration_module


@dataclass
class WorkflowIssue:
    severity: str
    code: str
    message: str
    node_id: str | None = None


@dataclass
class WorkflowReport:
    format: str
    node_count: int
    link_count: int
    node_types: dict[str, int]
    missing_node_types: list[str]
    input_files: list[str]
    model_candidates: list[str]
    execution_order: list[str]
    issues: list[dict[str, Any]]
    integrations: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_format(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("nodes"), list):
        return "ui"
    if isinstance(data, dict) and data and all(isinstance(v, dict) for v in data.values()):
        if any("class_type" in v for v in data.values()):
            return "api"
    return "unknown"


def _ui_nodes(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in data.get("nodes", []) if isinstance(n, dict)]


def _api_nodes(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(str(k), v) for k, v in data.items() if isinstance(v, dict)]


def _extract_strings(value: Any, result: list[str]) -> None:
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            _extract_strings(child, result)
    elif isinstance(value, list):
        for child in value:
            _extract_strings(child, result)


def analyze_workflow(value: str | dict[str, Any], live_registry: dict[str, Any] | None = None) -> WorkflowReport:
    data = load_json(value, default={})
    fmt = detect_format(data)
    issues: list[WorkflowIssue] = []
    registry = live_registry if live_registry is not None else get_live_node_registry()
    node_types: Counter[str] = Counter()
    input_files: set[str] = set()
    model_candidates: set[str] = set()
    order: list[str] = []
    link_count = 0

    if fmt == "ui":
        nodes = _ui_nodes(data)
        ids = {str(n.get("id")) for n in nodes}
        adjacency: dict[str, set[str]] = defaultdict(set)
        indegree: Counter[str] = Counter({node_id: 0 for node_id in ids})
        links = data.get("links", []) if isinstance(data.get("links"), list) else []
        link_count = len(links)
        for link in links:
            if not isinstance(link, list) or len(link) < 5:
                issues.append(WorkflowIssue("warning", "malformed_link", "A workflow link is malformed."))
                continue
            source, target = str(link[1]), str(link[3])
            if source not in ids or target not in ids:
                issues.append(WorkflowIssue("error", "dangling_link", f"Link references missing node {source} or {target}."))
                continue
            if target not in adjacency[source]:
                adjacency[source].add(target)
                indegree[target] += 1
        queue = deque(sorted(k for k, v in indegree.items() if v == 0))
        while queue:
            current = queue.popleft()
            order.append(current)
            for nxt in sorted(adjacency[current]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(ids):
            issues.append(WorkflowIssue("warning", "cycle_or_disconnected", "The workflow contains a cycle or graph data that cannot be topologically ordered."))
            order.extend(sorted(ids.difference(order)))
        for node in nodes:
            node_id = str(node.get("id"))
            node_type = str(node.get("type") or "Unknown")
            node_types[node_type] += 1
            values: list[str] = []
            _extract_strings(node.get("widgets_values", []), values)
            for item in values:
                lowered = item.lower()
                if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".flac", ".mp4", ".mov", ".mkv")):
                    input_files.add(item)
                if lowered.endswith((".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin")):
                    model_candidates.add(item)
            if not node_type or node_type == "Unknown":
                issues.append(WorkflowIssue("error", "missing_node_type", "Node has no type.", node_id))
    elif fmt == "api":
        nodes = _api_nodes(data)
        ids = {node_id for node_id, _ in nodes}
        adjacency: dict[str, set[str]] = defaultdict(set)
        indegree: Counter[str] = Counter({node_id: 0 for node_id in ids})
        for node_id, node in nodes:
            node_type = str(node.get("class_type") or "Unknown")
            node_types[node_type] += 1
            inputs = node.get("inputs", {})
            if not isinstance(inputs, dict):
                issues.append(WorkflowIssue("error", "invalid_inputs", "Node inputs must be an object.", node_id))
                inputs = {}
            for input_value in inputs.values():
                if isinstance(input_value, list) and len(input_value) >= 2 and str(input_value[0]) in ids:
                    source = str(input_value[0])
                    if node_id not in adjacency[source]:
                        adjacency[source].add(node_id)
                        indegree[node_id] += 1
                        link_count += 1
            values: list[str] = []
            _extract_strings(inputs, values)
            for item in values:
                lowered = item.lower()
                if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".flac", ".mp4", ".mov", ".mkv")):
                    input_files.add(item)
                if lowered.endswith((".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin")):
                    model_candidates.add(item)
        queue = deque(sorted(k for k, v in indegree.items() if v == 0))
        while queue:
            current = queue.popleft()
            order.append(current)
            for nxt in sorted(adjacency[current]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        order.extend(sorted(ids.difference(order)))
    else:
        issues.append(WorkflowIssue("error", "unknown_format", "Input is not a recognized ComfyUI UI workflow or API prompt graph."))
        nodes = []

    missing = []
    if registry:
        missing = sorted(t for t in node_types if t not in registry and t not in {"Reroute", "Note"})
        for node_type in missing:
            issues.append(WorkflowIssue("error", "missing_node_class", f"Node class is not registered in this ComfyUI instance: {node_type}"))

    integrations: dict[str, Any] = {}
    for entry in match_integrations(workflow=data):
        module_name = str(entry.get("module") or "")
        inspect_name = str(entry.get("inspect_function") or "")
        if not module_name or not inspect_name:
            continue
        try:
            module = load_integration_module(entry)
            inspector = getattr(module, inspect_name, None)
            if callable(inspector):
                integrations[str(entry.get("id"))] = inspector(data)
        except Exception as exc:
            integrations[str(entry.get("id"))] = {
                "detected": True,
                "issues": [f"Integration inspection failed: {type(exc).__name__}: {exc}"],
                "warnings": [],
                "recommendations": [],
            }

    return WorkflowReport(
        format=fmt,
        node_count=len(nodes),
        link_count=link_count,
        node_types=dict(sorted(node_types.items())),
        missing_node_types=missing,
        input_files=sorted(input_files),
        model_candidates=sorted(model_candidates),
        execution_order=order,
        issues=[asdict(issue) for issue in issues],
        integrations=integrations,
    )


def validate_workflow(value: str | dict[str, Any], strict: bool = False) -> dict[str, Any]:
    report = analyze_workflow(value)
    errors = [i for i in report.issues if i["severity"] == "error"]
    warnings = [i for i in report.issues if i["severity"] == "warning"]
    valid = not errors and (not strict or not warnings)
    return {"valid": valid, "strict": strict, "report": report.to_dict()}


def repair_workflow(value: str | dict[str, Any]) -> dict[str, Any]:
    original = load_json(value, default={})
    repaired = copy.deepcopy(original)
    changes: list[dict[str, Any]] = []
    fmt = detect_format(repaired)
    if fmt == "api":
        normalized: dict[str, Any] = {}
        for key, node in repaired.items():
            node_id = str(key)
            if node_id != key:
                changes.append({"path": str(key), "action": "normalized_node_id", "value": node_id})
            if not isinstance(node, dict):
                continue
            if "inputs" not in node or not isinstance(node.get("inputs"), dict):
                node["inputs"] = {}
                changes.append({"path": node_id, "action": "created_inputs_object"})
            normalized[node_id] = node
        repaired = normalized
    elif fmt == "ui":
        nodes = repaired.get("nodes", [])
        if not isinstance(nodes, list):
            repaired["nodes"] = []
            changes.append({"path": "nodes", "action": "replaced_invalid_nodes"})
        if not isinstance(repaired.get("links"), list):
            repaired["links"] = []
            changes.append({"path": "links", "action": "created_links_array"})
    return {
        "format": fmt,
        "changed": bool(changes),
        "changes": changes,
        "original": original,
        "repaired": repaired,
        "validation": validate_workflow(repaired),
    }


def load_workflow_collection(value: str | dict | list) -> list[dict[str, Any]]:
    parsed = load_json(value, default=[])
    if isinstance(parsed, dict):
        if "workflows" in parsed and isinstance(parsed["workflows"], list):
            parsed = parsed["workflows"]
        else:
            parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValueError("Workflow collection must be one workflow object or a list of workflow objects/paths.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(parsed, 1):
        if isinstance(item, str) and Path(item).expanduser().is_file():
            workflow = json.loads(Path(item).expanduser().read_text(encoding="utf-8"))
            result.append({"name": Path(item).stem, "source": str(Path(item).expanduser()), "workflow": workflow})
        elif isinstance(item, dict) and "workflow" in item:
            result.append({"name": str(item.get("name") or f"workflow-{index}"), "source": item.get("source"), "workflow": item["workflow"]})
        elif isinstance(item, dict):
            result.append({"name": f"workflow-{index}", "source": None, "workflow": item})
        else:
            raise ValueError(f"Unsupported workflow entry at index {index}.")
    return result
