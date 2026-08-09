from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from collections import defaultdict, deque
from typing import Any, Mapping, Sequence

from .node_catalog import catalog_contract_hash, classify_node_origin, node_schema_hash

GRAPH_PATCH_SCHEMA = "comfyui-pi.workflow-graph-patch.v1"
_ALIAS = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_HEAVY_TERMS = {
    "loader",
    "checkpoint",
    "model",
    "sampler",
    "save",
    "output",
    "preview",
    "api",
    "partner",
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def workflow_graph_hash(workflow: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(workflow).encode("utf-8")).hexdigest()


def _node_id(node: Mapping[str, Any]) -> str:
    return str(node.get("id"))


def _schema_inputs(info: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    declaration = 0
    socket_index = 0
    raw_input = info.get("input")
    input_root = raw_input if isinstance(raw_input, Mapping) else {}
    for group_name in ("required", "optional"):
        group = input_root.get(group_name)
        if not isinstance(group, Mapping):
            continue
        for name, spec in group.items():
            dtype = spec[0] if isinstance(spec, list) and spec else None
            connectable = isinstance(dtype, str)
            metadata = spec[1] if isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], Mapping) else {}
            result.append(
                {
                    "name": str(name),
                    "type": str(dtype) if connectable else "",
                    "input_index": declaration,
                    "occurrence_index": 0,
                    "socket_index": socket_index if connectable else None,
                    "mode": "slot" if connectable else "widget",
                    "choices": list(dtype) if isinstance(dtype, list) else None,
                    "metadata": dict(metadata),
                }
            )
            declaration += 1
            if connectable:
                socket_index += 1
    return result


def _schema_outputs(info: Mapping[str, Any]) -> list[dict[str, Any]]:
    outputs = info.get("output") if isinstance(info.get("output"), list) else []
    names = info.get("output_name") if isinstance(info.get("output_name"), list) else []
    result: list[dict[str, Any]] = []
    for index, dtype in enumerate(outputs):
        result.append(
            {
                "name": str(names[index] if index < len(names) else f"output_{index}"),
                "type": str(dtype),
                "output_index": index,
            }
        )
    return result


def _matches_node(query: str, node_type: str, info: Mapping[str, Any]) -> int:
    q = query.strip().casefold()
    if not q:
        return 0
    display = str(info.get("display_name") or node_type)
    category = str(info.get("category") or "")
    aliases = info.get("search_aliases") if isinstance(info.get("search_aliases"), list) else []
    if q == node_type.casefold():
        return 100
    if q == display.casefold():
        return 90
    if any(q == str(alias).casefold() for alias in aliases):
        return 80
    haystack = " ".join((node_type, display, category, *map(str, aliases))).casefold()
    words = [word for word in re.findall(r"[a-z0-9]+", q) if len(word) > 1]
    return sum(5 for word in words if word in haystack)


def resolve_node_type(query: str, catalog: Mapping[str, Any]) -> dict[str, Any]:
    if query in catalog and isinstance(catalog[query], dict):
        return {"valid": True, "node_type": query}
    ranked = sorted(
        (-_matches_node(query, str(name), info), str(name))
        for name, info in catalog.items()
        if isinstance(info, Mapping) and _matches_node(query, str(name), info) > 0
    )
    if not ranked:
        return {"valid": False, "needs_choice": False, "error": f"No loaded node matches {query!r}."}
    best = -ranked[0][0]
    choices = [name for neg, name in ranked if -neg == best]
    if len(choices) != 1:
        return {
            "valid": False,
            "needs_choice": True,
            "choices": choices[:12],
            "error": f"Node request {query!r} is ambiguous.",
        }
    return {"valid": True, "node_type": choices[0]}


def _resolve_output(info: Mapping[str, Any], requested: str | int | None) -> dict[str, Any]:
    outputs = _schema_outputs(info)
    if isinstance(requested, int):
        matches = [item for item in outputs if item["output_index"] == requested]
    elif requested not in (None, ""):
        q = str(requested).casefold()
        matches = [item for item in outputs if item["name"].casefold() == q]
    else:
        matches = outputs if len(outputs) == 1 else []
    if len(matches) != 1:
        raise ValueError(
            f"Output {requested!r} is ambiguous or absent; candidates: {[item['name'] for item in outputs]}"
        )
    return dict(matches[0])


def _resolve_input(info: Mapping[str, Any], requested: str | int | None) -> dict[str, Any]:
    inputs = _schema_inputs(info)
    if isinstance(requested, int):
        matches = [item for item in inputs if item["input_index"] == requested]
    elif requested not in (None, ""):
        q = str(requested).casefold()
        matches = [item for item in inputs if item["name"].casefold() == q]
    else:
        connectable = [item for item in inputs if item["mode"] == "slot"]
        matches = connectable if len(connectable) == 1 else []
    if len(matches) != 1:
        raise ValueError(
            f"Input {requested!r} is ambiguous or absent; candidates: {[item['name'] for item in inputs]}"
        )
    item = dict(matches[0])
    item.pop("choices", None)
    item.pop("metadata", None)
    return item


def _types_compatible(left: str, right: str) -> bool:
    return not left or not right or left == "*" or right == "*" or left == right


def _validate_values(node_type: str, info: Mapping[str, Any], values: Mapping[str, Any]) -> list[str]:
    inputs = {item["name"]: item for item in _schema_inputs(info)}
    issues: list[str] = []
    for key, value in values.items():
        item = inputs.get(str(key))
        if item is None:
            issues.append(f"{node_type} has no live input/widget named {key!r}.")
            continue
        choices = item.get("choices")
        if isinstance(choices, list) and choices and value not in choices:
            issues.append(f"{node_type}.{key} value {value!r} is not one of the live choices.")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = metadata.get("min")
            maximum = metadata.get("max")
            if isinstance(minimum, (int, float)) and value < minimum:
                issues.append(f"{node_type}.{key} value {value!r} is below live minimum {minimum!r}.")
            if isinstance(maximum, (int, float)) and value > maximum:
                issues.append(f"{node_type}.{key} value {value!r} is above live maximum {maximum!r}.")
    return issues


def _would_cycle(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> bool:
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {node: 0 for node in nodes}
    for source, target in edges:
        indegree.setdefault(source, 0)
        indegree.setdefault(target, 0)
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1
    queue = deque(node for node, degree in indegree.items() if degree == 0)
    seen = 0
    while queue:
        current = queue.popleft()
        seen += 1
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return seen != len(indegree)


def _existing_workflow_edges(workflow: Mapping[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    links = workflow.get("links")
    if not isinstance(links, list):
        return result
    for link in links:
        if isinstance(link, list) and len(link) >= 5:
            result.append((f"existing:{link[1]}", f"existing:{link[3]}"))
        elif isinstance(link, Mapping):
            source = link.get("origin_id", link.get("source"))
            target = link.get("target_id", link.get("target"))
            if source is not None and target is not None:
                result.append((f"existing:{source}", f"existing:{target}"))
    return result


def _safe_converter_candidate(node_type: str, info: Mapping[str, Any]) -> bool:
    origin = classify_node_origin(dict(info))
    if origin == "partner" or bool(info.get("api_node")) or bool(info.get("output_node")):
        return False
    text = " ".join(
        (
            node_type,
            str(info.get("display_name") or ""),
            str(info.get("category") or ""),
        )
    ).casefold()
    return not any(term in text for term in _HEAVY_TERMS)


def _converter_candidates(
    source_type: str,
    target_type: str,
    catalog: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for node_type, info in catalog.items():
        if not isinstance(info, Mapping) or not _safe_converter_candidate(str(node_type), info):
            continue
        inputs = [item for item in _schema_inputs(info) if item["mode"] == "slot"]
        outputs = _schema_outputs(info)
        incoming = [item for item in inputs if _types_compatible(source_type, str(item["type"]))]
        outgoing = [item for item in outputs if _types_compatible(str(item["type"]), target_type)]
        if len(incoming) == 1 and len(outgoing) == 1:
            inp = dict(incoming[0]); inp.pop("choices", None); inp.pop("metadata", None)
            candidates.append(
                {
                    "node_type": str(node_type),
                    "schema_hash": node_schema_hash(str(node_type), info),
                    "input": inp,
                    "output": dict(outgoing[0]),
                }
            )
    return candidates


def compile_graph_patch(
    request: Mapping[str, Any],
    workflow: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    workflow_identity: str = "",
    selected_node_ids: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Compile semantic JSON into an immutable, live-schema-pinned graph transaction."""
    if not isinstance(workflow, Mapping) or not isinstance(workflow.get("nodes", []), list):
        raise ValueError("A serialized ComfyUI UI workflow is required.")
    create_requests = request.get("nodes") or request.get("create_nodes") or []
    update_requests = request.get("updates") or request.get("update_nodes") or []
    remove_requests = request.get("remove_nodes") or []
    edge_requests = request.get("connections") or request.get("add_edges") or []
    remove_edges = request.get("remove_edges") or []
    if not all(
        isinstance(value, list)
        for value in (create_requests, update_requests, remove_requests, edge_requests, remove_edges)
    ):
        raise ValueError("GraphPatch list fields must be arrays.")

    selected = [str(value) for value in (selected_node_ids or [])]
    existing = {
        str(node.get("id")): node
        for node in workflow.get("nodes", [])
        if isinstance(node, dict)
    }
    aliases: dict[str, dict[str, Any]] = {}
    create_nodes: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    def add_create(item: Mapping[str, Any], index: int, *, inferred: bool = False) -> dict[str, Any] | None:
        query = str(
            item.get("node_type")
            or item.get("type")
            or item.get("role")
            or item.get("search")
            or ""
        ).strip()
        resolved = resolve_node_type(query, catalog)
        if not resolved.get("valid"):
            if resolved.get("needs_choice"):
                raise LookupError(canonical_json({
                    "path": f"nodes[{index}]",
                    "choices": resolved.get("choices", []),
                    "error": resolved.get("error"),
                }))
            issues.append(
                {
                    "code": "node_not_loaded",
                    "path": f"nodes[{index}]",
                    "message": resolved.get("error"),
                }
            )
            return None
        node_type = str(resolved["node_type"])
        info = catalog[node_type]
        alias = str(item.get("alias") or f"node_{index + 1}").strip()
        if not _ALIAS.fullmatch(alias):
            issues.append({"code": "invalid_alias", "path": f"nodes[{index}].alias"})
            return None
        if alias in aliases:
            issues.append({"code": "duplicate_alias", "path": f"nodes[{index}].alias"})
            return None
        values = copy.deepcopy(dict(item.get("values") or {}))
        for message in _validate_values(node_type, info, values):
            issues.append({"code": "invalid_value", "path": f"nodes[{index}].values", "message": message})
        spec = {
            "alias": alias,
            "node_type": node_type,
            "schema_hash": node_schema_hash(node_type, info),
            "values": values,
            "layout_hint": copy.deepcopy(item.get("layout") or item.get("layout_hint")),
            "inferred": bool(inferred),
        }
        aliases[alias] = spec
        create_nodes.append(spec)
        return spec

    try:
        for index, item in enumerate(create_requests):
            if isinstance(item, str):
                item = {"node_type": item}
            if not isinstance(item, Mapping):
                issues.append({"code": "invalid_create", "path": f"nodes[{index}]"})
                continue
            add_create(item, index)
    except LookupError as exc:
        payload = json.loads(str(exc))
        return {"valid": False, "needs_choice": True, **payload}

    def existing_candidates(ref: Mapping[str, Any]) -> list[dict[str, Any]]:
        if ref.get("selected") is True:
            return [existing[node_id] for node_id in selected if node_id in existing]
        if ref.get("title") not in (None, ""):
            wanted = str(ref.get("title")).casefold()
            return [node for node in existing.values() if str(node.get("title") or "").casefold() == wanted]
        wanted_type = str(ref.get("node_type") or ref.get("type") or "")
        if wanted_type:
            return [node for node in existing.values() if str(node.get("type") or "") == wanted_type]
        return []

    def ref_type(ref: Any) -> tuple[dict[str, Any], str]:
        if isinstance(ref, Mapping):
            if "node_id" in ref:
                node_id = str(ref["node_id"])
                node = existing.get(node_id)
                if not node:
                    raise ValueError(f"Existing node {node_id} does not exist.")
                return {"node_id": node_id}, str(node.get("type") or "")
            if "alias" in ref:
                ref = ref.get("alias")
            else:
                matches = existing_candidates(ref)
                if len(matches) != 1:
                    label = "selected node" if ref.get("selected") is True else "existing node selector"
                    raise ValueError(
                        f"{label} matched {len(matches)} nodes; a deterministic single match is required."
                    )
                node = matches[0]
                return {"node_id": str(node.get("id"))}, str(node.get("type") or "")
        key = str(ref or "")
        if key in aliases:
            return {"alias": key}, str(aliases[key]["node_type"])
        if key in existing:
            return {"node_id": key}, str(existing[key].get("type") or "")
        raise ValueError(f"Unknown node reference: {ref!r}")

    def ref_key(ref: Mapping[str, Any]) -> str:
        if "node_id" in ref:
            return f"existing:{ref['node_id']}"
        return f"new:{ref.get('alias')}"

    add_edges: list[dict[str, Any]] = []
    symbolic_edges = _existing_workflow_edges(workflow)
    allow_inferred = bool(request.get("allow_inferred_converters", True))
    for index, item in enumerate(edge_requests):
        if not isinstance(item, Mapping):
            issues.append({"code": "invalid_edge", "path": f"connections[{index}]"})
            continue
        try:
            sref, stype = ref_type(item.get("source") or item.get("from"))
            tref, ttype = ref_type(item.get("target") or item.get("to"))
            if stype not in catalog or ttype not in catalog:
                raise ValueError("Edge endpoint node type is not in the live catalog.")
            sinfo = catalog[stype]
            tinfo = catalog[ttype]
            output = _resolve_output(
                sinfo,
                item.get("output") if "output" in item else item.get("source_output"),
            )
            target = _resolve_input(
                tinfo,
                item.get("input") if "input" in item else item.get("target_input"),
            )
            if target["mode"] != "slot":
                raise ValueError(f"Input {target['name']} is a widget, not a connectable slot.")
            source_endpoint = {
                "ref": sref,
                "node_type": stype,
                "schema_hash": node_schema_hash(stype, sinfo),
                **output,
            }
            target_endpoint = {
                "ref": tref,
                "node_type": ttype,
                "schema_hash": node_schema_hash(ttype, tinfo),
                **target,
            }
            if _types_compatible(str(output["type"]), str(target["type"])):
                add_edges.append({"source": source_endpoint, "target": target_endpoint, "inferred": False})
                symbolic_edges.append((ref_key(sref), ref_key(tref)))
                continue

            candidates = _converter_candidates(str(output["type"]), str(target["type"]), catalog)
            if not allow_inferred:
                raise ValueError(
                    f"Incompatible connection {stype}.{output['name']} ({output['type']}) -> "
                    f"{ttype}.{target['name']} ({target['type']}); inferred converters are disabled."
                )
            if len(candidates) > 1:
                return {
                    "valid": False,
                    "needs_choice": True,
                    "path": f"connections[{index}]",
                    "error": "More than one safe one-hop converter can satisfy this connection.",
                    "choices": [candidate["node_type"] for candidate in candidates[:12]],
                }
            if not candidates:
                raise ValueError(
                    f"Incompatible connection {stype}.{output['name']} ({output['type']}) -> "
                    f"{ttype}.{target['name']} ({target['type']}); no unique safe local converter was found."
                )
            converter = candidates[0]
            alias = f"converter_{index + 1}"
            serial = 1
            while alias in aliases:
                serial += 1
                alias = f"converter_{index + 1}_{serial}"
            create_spec = {
                "alias": alias,
                "node_type": converter["node_type"],
                "schema_hash": converter["schema_hash"],
                "values": {},
                "layout_hint": None,
                "inferred": True,
            }
            aliases[alias] = create_spec
            create_nodes.append(create_spec)
            cref = {"alias": alias}
            converter_source = {
                "ref": cref,
                "node_type": converter["node_type"],
                "schema_hash": converter["schema_hash"],
                **converter["output"],
            }
            converter_target = {
                "ref": cref,
                "node_type": converter["node_type"],
                "schema_hash": converter["schema_hash"],
                **converter["input"],
            }
            add_edges.extend(
                [
                    {"source": source_endpoint, "target": converter_target, "inferred": True},
                    {"source": converter_source, "target": target_endpoint, "inferred": True},
                ]
            )
            symbolic_edges.extend(
                [
                    (ref_key(sref), ref_key(cref)),
                    (ref_key(cref), ref_key(tref)),
                ]
            )
        except ValueError as exc:
            issues.append(
                {"code": "invalid_edge", "path": f"connections[{index}]", "message": str(exc)}
            )

    graph_nodes = sorted({endpoint for edge in symbolic_edges for endpoint in edge})
    if _would_cycle(graph_nodes, symbolic_edges):
        issues.append(
            {
                "code": "cycle",
                "path": "connections",
                "message": "Requested edges would make the workflow cyclic.",
            }
        )

    update_nodes: list[dict[str, Any]] = []
    for index, item in enumerate(update_requests):
        if not isinstance(item, Mapping):
            issues.append({"code": "invalid_update", "path": f"updates[{index}]"})
            continue
        try:
            ref, node_type = ref_type(item.get("ref") or item.get("node_id") or item.get("alias") or item.get("selector"))
            info = catalog.get(node_type)
            if not isinstance(info, Mapping):
                raise ValueError(f"Node type {node_type!r} is not loaded.")
            values = copy.deepcopy(dict(item.get("values") or item.get("set_values") or {}))
            for message in _validate_values(node_type, info, values):
                issues.append({"code": "invalid_value", "path": f"updates[{index}].values", "message": message})
            update_nodes.append(
                {
                    "ref": ref,
                    "node_type": node_type,
                    "schema_hash": node_schema_hash(node_type, info),
                    "expected_values": copy.deepcopy(dict(item.get("expected_values") or {})),
                    "set_values": values,
                    "layout_hint": copy.deepcopy(item.get("layout") or item.get("layout_hint")),
                }
            )
        except ValueError as exc:
            issues.append({"code": "invalid_update", "path": f"updates[{index}]", "message": str(exc)})

    compiled_remove_nodes: list[dict[str, Any]] = []
    for index, item in enumerate(remove_requests):
        try:
            ref, node_type = ref_type(item)
            info = catalog.get(node_type)
            if not isinstance(info, Mapping):
                raise ValueError(f"Node type {node_type!r} is not loaded.")
            compiled_remove_nodes.append(
                {
                    "ref": ref,
                    "node_type": node_type,
                    "schema_hash": node_schema_hash(node_type, info),
                }
            )
        except ValueError as exc:
            issues.append({"code": "invalid_remove", "path": f"remove_nodes[{index}]", "message": str(exc)})

    if issues:
        return {"valid": False, "needs_choice": False, "issues": issues}

    plan = {
        "operation": "patch",
        "expected_workflow_identity": str(
            workflow_identity or request.get("expected_workflow_identity") or ""
        ),
        "expected_graph_hash": workflow_graph_hash(workflow),
        "create_nodes": create_nodes,
        "update_nodes": update_nodes,
        "remove_edges": copy.deepcopy(remove_edges),
        "add_edges": add_edges,
        "remove_nodes": compiled_remove_nodes,
        "preserve_unmentioned_state": True,
    }
    envelope = {
        "graph_patch_schema": GRAPH_PATCH_SCHEMA,
        "application_id": str(
            request.get("application_id") or f"comfyui-pi-{uuid.uuid4().hex}"
        ),
        "expected_catalog_hash": catalog_contract_hash(catalog),
        "plan": plan,
    }
    envelope["patch_hash"] = hashlib.sha256(
        canonical_json(envelope).encode("utf-8")
    ).hexdigest()
    return {
        "valid": True,
        "needs_choice": False,
        "apply_request": envelope,
        "plan": plan,
        "catalog_hash": envelope["expected_catalog_hash"],
        "patch_hash": envelope["patch_hash"],
    }
