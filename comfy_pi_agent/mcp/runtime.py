from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..compat import get_comfy_user_directory
from .browser_broker import BROWSER_TOOL_BROKER
from .catalog import tool_spec
from .runtime_context import current_base_url
from .security import SafetySettings, authorize_tool, load_safety_settings


@dataclass
class ToolContext:
    base_url: str
    safety: SafetySettings
    browser: Any = BROWSER_TOOL_BROKER

    @classmethod
    def current(cls, *, base_url: str = "") -> "ToolContext":
        settings_path = get_comfy_user_directory() / "pi-agent" / "mcp" / "safety.json"
        return cls(str(base_url or current_base_url()).rstrip("/"), load_safety_settings(settings_path))


async def invoke_tool(name: str, parameters: dict[str, Any] | None = None, *, context: ToolContext | None = None) -> Any:
    spec = tool_spec(name)
    ctx = context or ToolContext.current()
    allowed, reason = authorize_tool(name, ctx.safety)
    if not allowed:
        return {"success": False, "error": "capability_disabled", "error_code": reason, "tool": name, "gate": spec.gate}
    module = importlib.import_module(f"{__package__}.families.{spec.family}")
    handler = getattr(module, "invoke", None)
    if not callable(handler):
        raise RuntimeError(f"MCP tool family {spec.family!r} has no invoke() handler.")
    return await handler(name, dict(parameters or {}), ctx)
