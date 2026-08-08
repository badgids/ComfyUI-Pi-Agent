from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any


MIN_NODE_SCREENSHOT_PADDING = 300
DEFAULT_WORKFLOW_SCREENSHOT_PADDING = 80
DEFAULT_SCREENSHOT_TIMEOUT = 35.0


@dataclass
class _PendingScreenshot:
    request_id: str
    payload: dict[str, Any]
    future: asyncio.Future
    claimed_at: float | None = None


class ScreenshotBroker:
    """Coordinate a screenshot request with the active ComfyUI browser.

    The Pi process cannot see the browser DOM, while the ComfyUI web extension can.
    A request waits here until the browser claims it, captures the live workflow, and
    posts the PNG bytes back. No screenshots are fabricated server-side.
    """

    def __init__(self) -> None:
        self._pending: dict[str, _PendingScreenshot] = {}

    @staticmethod
    def normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(payload or {})
        mode = str(raw.get("mode") or "workflow").strip().lower()
        if mode not in {"workflow", "node"}:
            raise ValueError("Screenshot mode must be 'workflow' or 'node'.")

        node_id = str(raw.get("node_id") or "").strip()
        if mode == "node" and not node_id:
            raise ValueError("node_id is required for a node screenshot.")

        try:
            requested_padding = int(raw.get("padding_px", DEFAULT_WORKFLOW_SCREENSHOT_PADDING))
        except (TypeError, ValueError):
            requested_padding = DEFAULT_WORKFLOW_SCREENSHOT_PADDING
        padding_px = (
            max(MIN_NODE_SCREENSHOT_PADDING, requested_padding)
            if mode == "node"
            else max(0, requested_padding)
        )

        try:
            pixel_ratio = float(raw.get("pixel_ratio", 1.5))
        except (TypeError, ValueError):
            pixel_ratio = 1.5
        pixel_ratio = max(1.0, min(3.0, pixel_ratio))

        return {
            "mode": mode,
            "node_id": node_id,
            "padding_px": padding_px,
            "pixel_ratio": pixel_ratio,
        }

    async def request(
        self,
        payload: dict[str, Any] | None,
        timeout: float = DEFAULT_SCREENSHOT_TIMEOUT,
    ) -> dict[str, Any]:
        normalized = self.normalize_payload(payload)
        request_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = _PendingScreenshot(
            request_id=request_id,
            payload=normalized,
            future=future,
        )
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
                **item.payload,
            }
        return None

    def complete(
        self,
        request_id: str,
        png_bytes: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        item = self._pending.get(str(request_id or ""))
        if not item or item.future.done():
            return False
        if not png_bytes:
            item.future.set_result({"ok": False, "error": "Browser returned an empty screenshot."})
            return True
        item.future.set_result({
            "ok": True,
            "png": bytes(png_bytes),
            "metadata": dict(metadata or {}),
        })
        return True

    def fail(self, request_id: str, error: str) -> bool:
        item = self._pending.get(str(request_id or ""))
        if not item or item.future.done():
            return False
        item.future.set_result({
            "ok": False,
            "error": str(error or "Browser screenshot failed."),
        })
        return True

    def pending_count(self) -> int:
        return sum(1 for item in self._pending.values() if not item.future.done())


SCREENSHOT_BROKER = ScreenshotBroker()
