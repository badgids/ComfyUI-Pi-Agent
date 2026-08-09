from __future__ import annotations

from typing import Any

from ..graph_patch import compile_graph_patch
from ..node_catalog import (
    NodeCatalogStore,
    catalog_contract_hash,
    fetch_live_catalog,
    node_schema_hash,
)


async def _compile(p: dict[str, Any], ctx: Any) -> Any:
    current = await ctx.browser.execute(
        "workflow_get_current_json",
        {"format": "workflow"},
        contract_revision=2,
        timeout=30.0,
    )
    workflow = current.get("workflow") if isinstance(current, dict) else None
    identity = str(current.get("workflow_identity") or "") if isinstance(current, dict) else ""
    selected = current.get("selected_node_ids") if isinstance(current, dict) else []
    catalog = fetch_live_catalog(ctx.base_url)
    request = p.get("request") if isinstance(p.get("request"), dict) else p
    return compile_graph_patch(
        request,
        workflow or {},
        catalog,
        workflow_identity=identity,
        selected_node_ids=selected if isinstance(selected, list) else [],
    )


def _schema_precondition_failure(node_type: str, expected: str, actual: str) -> dict[str, Any]:
    return {
        "success": False,
        "applied": False,
        "error": {
            "code": "node_schema_precondition_failed",
            "message": f"Node schema changed for {node_type}.",
            "details": {
                "expected_schema_hash": expected,
                "actual_schema_hash": actual,
            },
        },
        "queued": False,
    }


def _record_verified_edges(request: dict[str, Any], result: dict[str, Any]) -> None:
    """Persist only lessons proven by a successful exact browser transaction."""
    verification = result.get("verification") if isinstance(result, dict) else None
    if not result.get("success") or not isinstance(verification, dict) or verification.get("valid") is not True:
        return
    plan = request.get("plan") if isinstance(request.get("plan"), dict) else {}
    edges = plan.get("add_edges") if isinstance(plan.get("add_edges"), list) else []
    if not edges:
        return
    store = NodeCatalogStore()
    try:
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source") if isinstance(edge.get("source"), dict) else {}
            target = edge.get("target") if isinstance(edge.get("target"), dict) else {}
            source_type = str(source.get("node_type") or "")
            target_type = str(target.get("node_type") or "")
            source_hash = str(source.get("schema_hash") or "")
            target_hash = str(target.get("schema_hash") or "")
            if not all((source_type, target_type, source_hash, target_hash)):
                continue
            payload = {
                "source_node_type": source_type,
                "source_schema_hash": source_hash,
                "source_output": str(source.get("name") or ""),
                "source_output_index": source.get("output_index"),
                "source_type": str(source.get("type") or ""),
                "target_node_type": target_type,
                "target_schema_hash": target_hash,
                "target_input": str(target.get("name") or ""),
                "target_input_index": target.get("input_index"),
                "target_socket_index": target.get("socket_index"),
                "target_type": str(target.get("type") or ""),
                "verified_by": "apply_workflow_graph_patch",
                "application_id": str(request.get("application_id") or ""),
            }
            source_key = (
                f"connect:{payload['source_output']}->{target_type}:{payload['target_input']}"
            )
            target_key = (
                f"accept:{source_type}:{payload['source_output']}->{payload['target_input']}"
            )
            store.put_lesson(source_type, source_hash, source_key, payload)
            store.put_lesson(target_type, target_hash, target_key, payload)
    finally:
        store.close()


async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    if name in {
        "compile_workflow_refinement_spec",
        "compile_workflow_spec",
        "plan_workflow",
        "plan_workflow_refinement",
        "resolve_workflow_spec",
    }:
        return await _compile(p, ctx)
    if name in {
        "apply_workflow_graph_patch",
        "apply_workflow_plan",
        "apply_workflow_refinement",
    }:
        request = p.get("request") if isinstance(p.get("request"), dict) else p
        catalog = fetch_live_catalog(ctx.base_url)
        expected_catalog = str(request.get("expected_catalog_hash") or "")
        actual_catalog = catalog_contract_hash(catalog)
        if expected_catalog and expected_catalog != actual_catalog:
            return {
                "success": False,
                "applied": False,
                "error": {
                    "code": "catalog_precondition_failed",
                    "message": "The live ComfyUI node catalog changed after this patch was compiled.",
                    "details": {
                        "expected_catalog_hash": expected_catalog,
                        "actual_catalog_hash": actual_catalog,
                    },
                },
                "queued": False,
            }
        plan = request.get("plan") if isinstance(request.get("plan"), dict) else {}
        schema_assertions: dict[tuple[str, str], None] = {}
        for section in ("create_nodes", "update_nodes", "remove_nodes"):
            for item in plan.get(section) or []:
                if isinstance(item, dict):
                    schema_assertions[(str(item.get("node_type") or ""), str(item.get("schema_hash") or ""))] = None
        for edge in plan.get("add_edges") or []:
            if not isinstance(edge, dict):
                continue
            for endpoint_name in ("source", "target"):
                endpoint = edge.get(endpoint_name)
                if isinstance(endpoint, dict):
                    schema_assertions[(str(endpoint.get("node_type") or ""), str(endpoint.get("schema_hash") or ""))] = None
        for node_type, expected_schema in schema_assertions:
            if not node_type:
                continue
            info = catalog.get(node_type)
            if not isinstance(info, dict):
                return {
                    "success": False,
                    "applied": False,
                    "error": {
                        "code": "node_schema_precondition_failed",
                        "message": f"Node type {node_type!r} is no longer loaded.",
                    },
                    "queued": False,
                }
            actual_schema = node_schema_hash(node_type, info)
            if expected_schema != actual_schema:
                return _schema_precondition_failure(node_type, expected_schema, actual_schema)
        result = await ctx.browser.execute(
            "apply_workflow_graph_patch",
            request,
            contract_revision=3,
            timeout=float(p.get("_timeout_seconds", 180) or 180),
        )
        if isinstance(result, dict):
            _record_verified_edges(request, result)
        return result
    raise KeyError(name)
