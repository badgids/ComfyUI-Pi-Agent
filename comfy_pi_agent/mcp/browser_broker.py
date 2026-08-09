from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class PendingBrowserTool:
    request_id: str
    tool_name: str
    parameters: dict[str, Any]
    contract_revision: int
    future: asyncio.Future
    claimed_at: float | None = None


class BrowserToolBroker:
    def __init__(self) -> None:
        self._pending: dict[str, PendingBrowserTool] = {}
        self._frontend: dict[str, Any] = {}

    def hello(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._frontend = dict(payload or {})
        return self.frontend_status()

    def frontend_status(self) -> dict[str, Any]:
        return {
            "connected": bool(self._frontend),
            **self._frontend,
            "pending": sum(1 for item in self._pending.values() if not item.future.done()),
        }

    async def execute(self, tool_name: str, parameters: dict[str, Any], *, contract_revision: int = 1, timeout: float = 60.0) -> Any:
        if not self._frontend:
            raise RuntimeError("requires_browser_bridge: open the current ComfyUI web UI so browser-native tools can run.")
        request_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = PendingBrowserTool(request_id, str(tool_name), dict(parameters or {}), int(contract_revision), future)
        try:
            return await asyncio.wait_for(future, timeout=max(1.0, float(timeout)))
        finally:
            self._pending.pop(request_id, None)

    def claim(self, reclaim_after: float = 5.0) -> dict[str, Any] | None:
        now = time.monotonic()
        for item in self._pending.values():
            if item.future.done():
                continue
            if item.claimed_at is not None and now - item.claimed_at < reclaim_after:
                continue
            item.claimed_at = now
            return {
                "request_id": item.request_id,
                "tool_name": item.tool_name,
                "parameters": item.parameters,
                "contract_revision": item.contract_revision,
            }
        return None

    def complete(self, request_id: str, payload: dict[str, Any]) -> bool:
        item = self._pending.get(str(request_id or ""))
        if not item or item.future.done():
            return False
        if payload.get("success") is False:
            error = RuntimeError(str(payload.get("error") or "browser tool execution failed"))
            setattr(error, "code", str(payload.get("error_code") or "tool_execution_failed"))
            setattr(error, "details", payload.get("error_details"))
            item.future.set_exception(error)
        else:
            item.future.set_result(payload.get("data", payload))
        return True


BROWSER_TOOL_BROKER = BrowserToolBroker()
