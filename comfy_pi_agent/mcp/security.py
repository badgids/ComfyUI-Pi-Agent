from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .catalog import TOOL_SPECS, tool_spec


@dataclass(frozen=True)
class SafetySettings:
    workflow_writes: bool = True
    custom_node_writes: bool = False
    git_writes: bool = False
    manager_mutations: bool = False
    process_control: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_safety_settings(path: str | Path | None = None) -> SafetySettings:
    values: dict[str, Any] = {}
    if path:
        candidate = Path(path).expanduser()
        if candidate.is_file():
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    values = loaded
            except Exception:
                values = {}
    defaults = SafetySettings()
    return SafetySettings(
        workflow_writes=_env_bool("COMFYUI_PI_ENABLE_WORKFLOW_WRITES", bool(values.get("workflow_writes", defaults.workflow_writes))),
        custom_node_writes=_env_bool("COMFYUI_PI_ENABLE_CUSTOM_NODE_WRITES", bool(values.get("custom_node_writes", defaults.custom_node_writes))),
        git_writes=_env_bool("COMFYUI_PI_ENABLE_GIT_WRITES", bool(values.get("git_writes", defaults.git_writes))),
        manager_mutations=_env_bool("COMFYUI_PI_ENABLE_MANAGER_MUTATIONS", bool(values.get("manager_mutations", defaults.manager_mutations))),
        process_control=_env_bool("COMFYUI_PI_ENABLE_PROCESS_CONTROL", bool(values.get("process_control", defaults.process_control))),
    )


def classify_tool(name: str) -> str:
    spec = TOOL_SPECS.get(str(name))
    return spec.risk if spec else "approval_required"


def gate_for_tool(name: str) -> str:
    spec = TOOL_SPECS.get(str(name))
    return spec.gate if spec else "unknown_tool"


def authorize_tool(name: str, settings: SafetySettings) -> tuple[bool, str]:
    try:
        spec = tool_spec(name)
    except KeyError:
        return False, "unknown_tool"
    if not spec.gate:
        return True, ""
    if not bool(getattr(settings, spec.gate, False)):
        return False, f"{spec.gate}_disabled"
    return True, ""


def capability_audit(settings: SafetySettings) -> dict[str, Any]:
    by_risk: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for spec in TOOL_SPECS.values():
        by_risk[spec.risk] = by_risk.get(spec.risk, 0) + 1
        by_family[spec.family] = by_family.get(spec.family, 0) + 1
    return {
        "tool_count": len(TOOL_SPECS),
        "risk_counts": by_risk,
        "family_counts": by_family,
        "server_gates": settings.to_dict(),
        "unknown_tools_fail_closed": True,
    }
