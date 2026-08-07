from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .agent_guidance import build_request_guidance
from .integrations.router import build_dynamic_integration_context


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
    args = parser.parse_args()
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
