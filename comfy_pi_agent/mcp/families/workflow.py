from __future__ import annotations
from typing import Any

async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    timeout = float(p.pop("_timeout_seconds", 120.0) or 120.0)
    return await ctx.browser.execute(name, p, contract_revision=2 if name in {"workflow_get_current_json", "apply_workflow_graph_patch"} else 1, timeout=timeout)
