from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from ..io_utils import load_json

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _PLUGIN_ROOT / "data" / "integrations" / "registry.json"


def load_integration_registry() -> dict[str, Any]:
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "1.0", "context_policy": {}, "integrations": []}
    if not isinstance(data, dict):
        return {"schema_version": "1.0", "context_policy": {}, "integrations": []}
    data.setdefault("integrations", [])
    data.setdefault("context_policy", {})
    return data


def _workflow_node_types(workflow: Any) -> set[str]:
    if workflow in (None, "", {}):
        return set()
    try:
        data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()
    if isinstance(data.get("nodes"), list):
        return {
            str(node.get("type"))
            for node in data["nodes"]
            if isinstance(node, dict) and node.get("type")
        }
    return {
        str(node.get("class_type"))
        for node in data.values()
        if isinstance(node, dict) and node.get("class_type")
    }


def match_integrations(
    workflow: Any = None,
    message: str = "",
    explicit_ids: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return only integrations relevant to this request/workflow.

    This function reads only the small registry manifest. It does not import any integration
    module and does not read any integration skill/knowledge file.
    """
    registry = load_integration_registry()
    node_types = _workflow_node_types(workflow)
    text = str(message or "").lower()
    explicit = {str(item) for item in (explicit_ids or [])}
    matched: list[dict[str, Any]] = []
    for entry in registry.get("integrations", []):
        if not isinstance(entry, dict):
            continue
        integration_id = str(entry.get("id") or "")
        node_ids = {str(item) for item in entry.get("node_ids", [])}
        terms = [str(item).lower() for item in entry.get("match_terms", []) if str(item).strip()]
        reason: list[str] = []
        if integration_id in explicit:
            reason.append("explicit")
        if node_types.intersection(node_ids):
            reason.append("workflow_node")
        if text and any(term in text for term in terms):
            reason.append("message")
        if reason:
            item = dict(entry)
            item["match_reason"] = reason
            matched.append(item)
    return matched


def _read_skill(entry: dict[str, Any], limit: int) -> str:
    path = str(entry.get("skill_path") or "").strip()
    if not path:
        return ""
    candidate = (_PLUGIN_ROOT / path).resolve()
    try:
        candidate.relative_to(_PLUGIN_ROOT.resolve())
    except Exception:
        return ""
    if not candidate.is_file():
        return ""
    try:
        text = candidate.read_text(encoding="utf-8")
    except Exception:
        return ""
    return text[: max(0, int(limit))]


def load_integration_module(entry: dict[str, Any]):
    module_name = str(entry.get("module") or "").strip()
    if not module_name:
        return None
    try:
        return importlib.import_module(module_name)
    except ImportError:
        # Repository-by-path ComfyUI loaders may give the parent package a generated name.
        # Import the adapter relative to this integrations package in that case.
        return importlib.import_module("." + module_name.rsplit(".", 1)[-1], package=__package__)


def _load_context_builder(entry: dict[str, Any]):
    function_name = str(entry.get("context_function") or "").strip()
    if not function_name:
        return None
    module = load_integration_module(entry)
    function = getattr(module, function_name, None) if module is not None else None
    return function if callable(function) else None


def _message_requests_full_skill(message: str) -> bool:
    text = str(message or "").lower()
    phrases = (
        "load full skill",
        "full integration guide",
        "complete integration guide",
        "complete node pack guide",
        "complete node-pack guide",
        "comprehensive tutorial",
        "complete tutorial",
        "thorough tutorial",
        "deep dive",
        "document every node",
        "explain every node",
    )
    return any(phrase in text for phrase in phrases)


def build_dynamic_integration_context(
    workflow: Any = None,
    message: str = "",
    explicit_ids: list[str] | tuple[str, ...] | set[str] | None = None,
    include_skill: bool | None = None,
    max_total_chars: int | None = None,
) -> dict[str, Any]:
    """Lazily load only node-pack knowledge relevant to the current request.

    At ComfyUI/Pi startup this function is not called, so no integration knowledge is
    injected. When called, the registry is matched first; only matching integration modules
    and their detailed skill files are imported/read.
    """
    registry = load_integration_registry()
    policy = registry.get("context_policy", {}) if isinstance(registry.get("context_policy"), dict) else {}
    total_limit = int(max_total_chars or policy.get("max_total_context_chars") or 24000)
    per_limit = int(policy.get("max_context_chars_per_integration") or 14000)
    matched = match_integrations(workflow=workflow, message=message, explicit_ids=explicit_ids)
    # Normal chat/workflow requests get the integration adapter's compact task-targeted
    # context only. The full SKILL.md is reserved for explicit deep documentation/tutorial
    # requests, or callers that deliberately pass include_skill=True.
    load_full_skill = _message_requests_full_skill(message) if include_skill is None else bool(include_skill)
    contexts: list[str] = []
    loaded: list[dict[str, Any]] = []
    remaining = max(0, total_limit)

    for entry in matched:
        if remaining <= 0:
            break
        builder = _load_context_builder(entry)
        compact = ""
        if builder is not None:
            try:
                compact = str(builder(workflow=workflow, message=message) or "")
            except TypeError:
                compact = str(builder(workflow, message) or "")
            except Exception as exc:
                compact = f"Integration context loader error for {entry.get('id')}: {type(exc).__name__}: {exc}"

        skill = _read_skill(entry, per_limit) if load_full_skill else ""
        pieces = [piece.strip() for piece in (compact, skill) if piece and piece.strip()]
        if not pieces:
            continue
        text = "\n\n".join(pieces)
        allowed = min(per_limit, remaining)
        text = text[:allowed]
        contexts.append(text)
        remaining -= len(text)
        loaded.append({
            "id": entry.get("id"),
            "display_name": entry.get("display_name"),
            "match_reason": entry.get("match_reason", []),
            "context_chars": len(text),
            "full_skill_loaded": bool(skill),
        })

    return {
        "loaded_integrations": loaded,
        "context": "\n\n---\n\n".join(contexts),
        "context_chars": sum(item["context_chars"] for item in loaded),
        "startup_injection": False,
        "policy": {
            "load_on_startup": False,
            "inject_only_when_matched": True,
            "max_total_context_chars": total_limit,
            "max_context_chars_per_integration": per_limit,
            "full_skill_auto_triggered": bool(load_full_skill and include_skill is None),
        },
    }


def integration_status(workflow: Any = None, message: str = "") -> dict[str, Any]:
    registry = load_integration_registry()
    matched = match_integrations(workflow=workflow, message=message)
    return {
        "registry_count": len(registry.get("integrations", [])),
        "matched": [
            {
                "id": entry.get("id"),
                "display_name": entry.get("display_name"),
                "match_reason": entry.get("match_reason", []),
            }
            for entry in matched
        ],
        "context_policy": registry.get("context_policy", {}),
        "note": "Integration modules and detailed knowledge are loaded only after a request/workflow match or explicit integration call.",
    }
