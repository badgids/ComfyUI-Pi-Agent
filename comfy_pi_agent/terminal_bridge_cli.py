from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .agent_guidance import build_request_guidance
from .context_handoff import ContextPressure, clamp_handoff_chars, clamp_threshold, create_handoff
from .integrations.router import build_dynamic_integration_context
from .pi_runtime import _extract_message_text


def _load_json(path: str) -> dict[str, Any]:
    candidate = Path(str(path or "")).expanduser()
    if not str(path or "").strip() or not candidate.is_file():
        return {}
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_workflow(path: str) -> Any:
    if not str(path or "").strip():
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_visible_messages(session_file: str) -> list[dict[str, str]]:
    path = Path(str(session_file or "")).expanduser()
    if not path.is_file():
        return []
    messages: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                try:
                    item = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                message = item.get("message")
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "")
                if role not in {"user", "assistant"}:
                    continue
                text = _extract_message_text(message).strip()
                if text:
                    messages.append({"role": role, "content": text})
    except Exception:
        return []
    return messages


def _workflow_digest(workflow: Any) -> str:
    if not isinstance(workflow, dict):
        return ""
    nodes = workflow.get("nodes")
    nodes = nodes if isinstance(nodes, list) else []
    counts: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or node.get("class_type") or "unknown")
        counts[node_type] = counts.get(node_type, 0) + 1
    links = workflow.get("links")
    return json.dumps(
        {
            "node_count": len(nodes),
            "link_count": len(links) if isinstance(links, list) else 0,
            "node_types": counts,
        },
        ensure_ascii=False,
    )[:6000]


def create_terminal_handoff(
    config_path: str,
    session_file: str,
    context_tokens: int,
    context_window: int,
    reason: str = "manual",
) -> dict[str, Any]:
    """Create ComfyUI-Pi's durable checkpoint without changing Pi's active session."""

    config = _load_json(config_path)
    tokens = max(0, int(context_tokens or 0))
    window = max(0, int(context_window or 0))
    threshold = clamp_threshold(config.get("handoff_threshold", 0.825))
    ratio = (tokens / window) if tokens > 0 and window > 0 else 0.0
    pressure = ContextPressure(
        context_tokens=tokens,
        context_window=window,
        ratio=ratio,
        threshold=threshold,
        should_handoff=bool(tokens > 0 and window > 0 and ratio >= threshold),
        source=f"pi_terminal_compaction_{str(reason or 'manual')}",
    )
    workflow_path = str(config.get("workflow_path") or "")
    workflow = _load_workflow(workflow_path)
    document = {
        "session_id": str(config.get("session_id") or "terminal"),
        "title": f"Pi terminal {str(config.get('session_id') or '')[:8]}",
        "project_directory": str(config.get("project_directory") or ""),
        "provider": str(config.get("provider") or ""),
        "model": str(config.get("model") or ""),
        "messages": _read_visible_messages(session_file),
    }
    metadata = create_handoff(
        session_id=document["session_id"],
        document=document,
        pressure=pressure,
        project_context=str(config.get("project_context") or ""),
        workflow_summary=_workflow_digest(workflow),
        workflow_context_path=workflow_path if workflow_path and Path(workflow_path).is_file() else "",
        routed_context=None,
        max_chars=clamp_handoff_chars(config.get("handoff_max_chars", 8000)),
        summarizer=None,
    )
    result = dict(metadata)
    result["compaction_reason"] = str(reason or "manual")
    result["pi_session_file"] = str(Path(session_file).expanduser())
    return result


def build_terminal_guidance(message: str, workflow_path: str = "", project_context: str = "") -> str:
    workflow = _load_workflow(workflow_path)
    guidance = build_request_guidance(message, workflow=workflow)
    routed = build_dynamic_integration_context(workflow=workflow, message=message)
    blocks = [
        str(guidance.get("core_contract") or "").strip(),
        str(guidance.get("task_envelope") or "").strip(),
        str(guidance.get("skill_context") or "").strip(),
        str(routed.get("context") or "").strip(),
    ]
    if str(project_context or "").strip():
        blocks.append("PROJECT CONTEXT (user supplied):\n" + str(project_context).strip()[:6000])
    return "\n\n".join(block for block in blocks if block).strip()[:24000]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sparse one-turn ComfyUI-Pi guidance for the Pi terminal bridge.")
    parser.add_argument("--message", default="")
    parser.add_argument("--message-file", default="")
    parser.add_argument("--workflow", default="")
    parser.add_argument("--project-context", default="")
    parser.add_argument("--create-handoff", action="store_true")
    parser.add_argument("--config", default="")
    parser.add_argument("--session-file", default="")
    parser.add_argument("--context-tokens", type=int, default=0)
    parser.add_argument("--context-window", type=int, default=0)
    parser.add_argument("--reason", default="manual")
    args = parser.parse_args()

    if args.create_handoff:
        result = create_terminal_handoff(
            args.config,
            args.session_file,
            args.context_tokens,
            args.context_window,
            args.reason,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    message = args.message
    if str(args.message_file or "").strip():
        try:
            message = Path(args.message_file).expanduser().read_text(encoding="utf-8")
        except Exception:
            # The bridge is advisory; a missing transient input file should degrade to the
            # explicit --message value rather than block the user's real Pi terminal.
            pass
    print(build_terminal_guidance(message, args.workflow, args.project_context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
