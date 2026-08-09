from __future__ import annotations

import asyncio
import json
import math
import shutil
import time
import uuid
from dataclasses import dataclass
from typing import Any


MIN_NODE_SCREENSHOT_PADDING = 300
EXACT_NODE_SCREENSHOT_MODE = "node_exact"
DEFAULT_WORKFLOW_SCREENSHOT_PADDING = 80
DEFAULT_SCREENSHOT_TIMEOUT = 35.0
DEFAULT_PLAYWRIGHT_VIEWPORT = (2200, 1800)
MAX_PLAYWRIGHT_VIEWPORT = (5000, 5000)


@dataclass
class _PendingScreenshot:
    request_id: str
    payload: dict[str, Any]
    future: asyncio.Future
    claimed_at: float | None = None


class ScreenshotBroker:
    """Coordinate a screenshot request with the active ComfyUI browser.

    The visible browser contributes the serialized UI workflow and current frontend
    storage settings. A separate Playwright page then loads that workflow into the
    same ComfyUI instance and takes the actual PNG with page.screenshot(clip=...).
    """

    def __init__(self) -> None:
        self._pending: dict[str, _PendingScreenshot] = {}

    @staticmethod
    def normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(payload or {})
        mode = str(raw.get("mode") or "workflow").strip().lower()
        if mode not in {"workflow", "node", EXACT_NODE_SCREENSHOT_MODE}:
            raise ValueError("Screenshot mode must be 'workflow', 'node', or 'node_exact'.")

        node_id = str(raw.get("node_id") or "").strip()
        node_type = str(raw.get("node_type") or "").strip()
        if mode == "node" and not node_id:
            raise ValueError("node_id is required for a node screenshot.")
        if mode == EXACT_NODE_SCREENSHOT_MODE and not (node_id or node_type):
            raise ValueError("node_id or node_type is required for an exact node image.")

        workflow = raw.get("workflow")
        if workflow is not None and (
            not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list)
        ):
            raise ValueError("Screenshot workflow override must be a serialized ComfyUI UI workflow.")

        try:
            requested_padding = int(raw.get("padding_px", DEFAULT_WORKFLOW_SCREENSHOT_PADDING))
        except (TypeError, ValueError):
            requested_padding = DEFAULT_WORKFLOW_SCREENSHOT_PADDING
        if mode == EXACT_NODE_SCREENSHOT_MODE:
            padding_px = 0
        elif mode == "node":
            padding_px = max(MIN_NODE_SCREENSHOT_PADDING, requested_padding)
        else:
            padding_px = max(0, requested_padding)

        try:
            pixel_ratio = float(raw.get("pixel_ratio", 1.5))
        except (TypeError, ValueError):
            pixel_ratio = 1.5
        pixel_ratio = max(1.0, min(3.0, pixel_ratio))

        normalized = {
            "mode": mode,
            "node_id": node_id,
            "node_type": node_type,
            "padding_px": padding_px,
            "pixel_ratio": pixel_ratio,
        }
        if workflow is not None:
            normalized["workflow"] = workflow
        return normalized

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
            item.future.set_result({"ok": False, "error": "Playwright returned an empty screenshot."})
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
            "error": str(error or "Playwright screenshot failed."),
        })
        return True

    def pending_count(self) -> int:
        return sum(1 for item in self._pending.values() if not item.future.done())


def _box_clip(box: dict[str, Any], padding: int) -> dict[str, float]:
    pad = max(0, int(padding))
    x = float(box["x"])
    y = float(box["y"])
    width = max(1.0, float(box["width"]))
    height = max(1.0, float(box["height"]))
    return {
        "x": max(0.0, x - pad),
        "y": max(0.0, y - pad),
        "width": width + pad * 2,
        "height": height + pad * 2,
    }


def _required_node_viewport(
    box: dict[str, Any],
    padding: int,
    current: dict[str, int],
    minimum_padding: int = MIN_NODE_SCREENSHOT_PADDING,
) -> dict[str, int]:
    pad = max(max(0, int(minimum_padding)), int(padding))
    required_width = int(math.ceil(float(box["width"]) + pad * 2 + 160))
    required_height = int(math.ceil(float(box["height"]) + pad * 2 + 160))
    return {
        "width": min(
            MAX_PLAYWRIGHT_VIEWPORT[0],
            max(int(current.get("width") or 0), DEFAULT_PLAYWRIGHT_VIEWPORT[0], required_width),
        ),
        "height": min(
            MAX_PLAYWRIGHT_VIEWPORT[1],
            max(int(current.get("height") or 0), DEFAULT_PLAYWRIGHT_VIEWPORT[1], required_height),
        ),
    }


def _storage_init_script(
    local_storage: dict[str, Any],
    session_storage: dict[str, Any],
) -> str:
    local_json = json.dumps({str(k): str(v) for k, v in (local_storage or {}).items() if v is not None})
    session_json = json.dumps({str(k): str(v) for k, v in (session_storage or {}).items() if v is not None})
    return f"""
(() => {{
  const localItems = {local_json};
  const sessionItems = {session_json};
  try {{
    for (const [key, value] of Object.entries(localItems)) localStorage.setItem(key, value);
  }} catch {{}}
  try {{
    for (const [key, value] of Object.entries(sessionItems)) sessionStorage.setItem(key, value);
  }} catch {{}}
}})();
"""


async def _launch_chromium(playwright: Any) -> Any:
    candidates = (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "msedge",
    )
    launch_errors: list[str] = []

    for executable in candidates:
        path = shutil.which(executable)
        if not path:
            continue
        try:
            return await playwright.chromium.launch(
                headless=True,
                executable_path=path,
                args=["--disable-dev-shm-usage"],
            )
        except Exception as exc:
            launch_errors.append(f"{path}: {exc}")

    try:
        return await playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )
    except Exception as exc:
        launch_errors.append(str(exc))
        details = "\n".join(launch_errors[-3:])
        raise RuntimeError(
            "Playwright is installed but no usable Chromium browser is available. "
            "Install one with `python -m playwright install chromium` or provide a "
            "system Chromium/Chrome executable on PATH."
            + (f"\nLaunch errors:\n{details}" if details else "")
        ) from exc


def _node_selector(node_id: str) -> str:
    escaped = str(node_id).replace("\\", "\\\\").replace('"', '\\"')
    return f'.lg-node[data-node-id="{escaped}"]'


async def _stable_locator_box(
    locator: Any,
    *,
    timeout_seconds: float = 5.0,
    sample_seconds: float = 0.08,
    stable_samples: int = 3,
) -> dict[str, float]:
    """Wait until the real Vue node root has stable measurable geometry."""
    deadline = time.monotonic() + max(0.5, float(timeout_seconds))
    wanted = max(2, int(stable_samples))
    last_signature: tuple[float, float, float, float] | None = None
    last_box: dict[str, float] | None = None
    stable = 0
    while time.monotonic() < deadline:
        box = await locator.bounding_box()
        if box and float(box.get("width") or 0) > 0 and float(box.get("height") or 0) > 0:
            signature = tuple(
                round(float(box[key]), 1) for key in ("x", "y", "width", "height")
            )
            if signature == last_signature:
                stable += 1
            else:
                last_signature = signature
                stable = 1
            last_box = {key: float(box[key]) for key in ("x", "y", "width", "height")}
            if stable >= wanted:
                return last_box
        await asyncio.sleep(max(0.02, float(sample_seconds)))
    if last_box is None:
        raise RuntimeError("ComfyUI rendered the Vue node without a measurable .lg-node bounding box.")
    raise RuntimeError("ComfyUI Vue node geometry did not settle before screenshot capture.")


async def capture_with_playwright(
    payload: dict[str, Any],
    *,
    base_url: str,
) -> dict[str, Any]:
    request_payload = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    request = ScreenshotBroker.normalize_payload(request_payload)

    workflow = payload.get("workflow")
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("Playwright capture requires the active serialized ComfyUI UI workflow.")

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "The Playwright screenshot backend is not installed. Install the ComfyUI-Pi "
            "screenshot extra with `python -m pip install -e '.[screenshots]'`, then install "
            "Chromium with `python -m playwright install chromium` if no system Chromium is available."
        ) from exc

    source_viewport = payload.get("viewport") if isinstance(payload.get("viewport"), dict) else {}
    viewport = {
        "width": min(
            MAX_PLAYWRIGHT_VIEWPORT[0],
            max(DEFAULT_PLAYWRIGHT_VIEWPORT[0], int(source_viewport.get("width") or 0)),
        ),
        "height": min(
            MAX_PLAYWRIGHT_VIEWPORT[1],
            max(DEFAULT_PLAYWRIGHT_VIEWPORT[1], int(source_viewport.get("height") or 0)),
        ),
    }
    local_storage = payload.get("local_storage") if isinstance(payload.get("local_storage"), dict) else {}
    session_storage = payload.get("session_storage") if isinstance(payload.get("session_storage"), dict) else {}

    capture_url = f"{str(base_url).rstrip('/')}/?comfyui_pi_playwright_capture=1"
    browser = None
    async with async_playwright() as playwright:
        try:
            browser = await _launch_chromium(playwright)
            context = await browser.new_context(
                viewport=viewport,
                device_scale_factor=request["pixel_ratio"],
                color_scheme="dark" if bool(payload.get("prefers_dark")) else "light",
            )
            await context.add_init_script(
                script=_storage_init_script(local_storage, session_storage)
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            await page.goto(capture_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_function(
                    """() =>
                      globalThis.__COMFYUI_PI_PLAYWRIGHT_CAPTURE_READY__ === true &&
                      typeof globalThis.__COMFYUI_PI_PREPARE_PLAYWRIGHT_CAPTURE__ === 'function'"""
                )
            except Exception as exc:
                raise RuntimeError(
                    "The ComfyUI capture page never reached the extension setup-ready state. "
                    "Real node/workflow capture requires the running frontend to finish app setup."
                ) from exc

            prepare_payload = {
                "workflow": workflow,
                "mode": request["mode"],
                "node_id": request["node_id"],
                "node_type": request["node_type"],
                "padding_px": request["padding_px"],
            }
            prepared = await page.evaluate(
                "(payload) => globalThis.__COMFYUI_PI_PREPARE_PLAYWRIGHT_CAPTURE__(payload)",
                prepare_payload,
            )
            await page.wait_for_selector(".lg-node[data-node-id]", state="attached")
            await page.wait_for_timeout(120)

            node_box: dict[str, float] | None = None
            node_capture = request["mode"] in {"node", EXACT_NODE_SCREENSHOT_MODE}
            if node_capture:
                locator = page.locator(_node_selector(request["node_id"])).first
                await locator.wait_for(state="visible")
                node_box = await _stable_locator_box(locator)

                required_viewport = _required_node_viewport(
                    node_box,
                    request["padding_px"],
                    viewport,
                    minimum_padding=(
                        0 if request["mode"] == EXACT_NODE_SCREENSHOT_MODE
                        else MIN_NODE_SCREENSHOT_PADDING
                    ),
                )
                if required_viewport != viewport:
                    viewport = required_viewport
                    await page.set_viewport_size(viewport)
                    prepared = await page.evaluate(
                        "(payload) => globalThis.__COMFYUI_PI_PREPARE_PLAYWRIGHT_CAPTURE__(payload)",
                        prepare_payload,
                    )
                    await page.wait_for_timeout(80)
                    node_box = await _stable_locator_box(locator)

                padding = int(request["padding_px"])
                if (
                    float(node_box["x"]) < padding
                    or float(node_box["y"]) < padding
                    or float(node_box["x"]) + float(node_box["width"]) + padding > viewport["width"]
                    or float(node_box["y"]) + float(node_box["height"]) + padding > viewport["height"]
                ):
                    raise RuntimeError(
                        f"Could not frame node {request['node_id']} with the required "
                        f"{padding}px margin on every side."
                    )
                clip = _box_clip(node_box, padding)
            else:
                boxes = await page.locator(".lg-node[data-node-id]").evaluate_all(
                    """(elements) => elements
                      .filter((el) => {
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                      })
                      .map((el) => {
                        const r = el.getBoundingClientRect();
                        return { x: r.x, y: r.y, width: r.width, height: r.height };
                      })"""
                )
                prepared_workflow_box = (
                    prepared.get("workflow_box") if isinstance(prepared, dict) else None
                )
                if isinstance(prepared_workflow_box, dict):
                    try:
                        if (
                            float(prepared_workflow_box.get("width") or 0) > 0
                            and float(prepared_workflow_box.get("height") or 0) > 0
                        ):
                            boxes.append(prepared_workflow_box)
                    except (TypeError, ValueError):
                        pass
                if not boxes:
                    raise RuntimeError("ComfyUI rendered no real Vue workflow nodes for the screenshot.")
                min_x = min(float(box["x"]) for box in boxes)
                min_y = min(float(box["y"]) for box in boxes)
                max_x = max(float(box["x"]) + float(box["width"]) for box in boxes)
                max_y = max(float(box["y"]) + float(box["height"]) for box in boxes)
                clip = _box_clip(
                    {
                        "x": min_x,
                        "y": min_y,
                        "width": max_x - min_x,
                        "height": max_y - min_y,
                    },
                    request["padding_px"],
                )

            page_width = float(viewport["width"])
            page_height = float(viewport["height"])
            clip["width"] = min(float(clip["width"]), max(1.0, page_width - float(clip["x"])))
            clip["height"] = min(float(clip["height"]), max(1.0, page_height - float(clip["y"])))

            png = await page.screenshot(
                type="png",
                clip=clip,
                animations="disabled",
                caret="hide",
                scale="device",
            )
            ratio = float(request["pixel_ratio"])
            prepared_node_type = (
                str(prepared.get("node_type") or "") if isinstance(prepared, dict) else ""
            )
            metadata = {
                "width": int(round(float(clip["width"]) * ratio)),
                "height": int(round(float(clip["height"]) * ratio)),
                "mode": request["mode"],
                "node_id": request["node_id"],
                "node_type": prepared_node_type or request["node_type"],
                "padding_px": request["padding_px"],
                "node_width_px": (
                    int(round(float(node_box["width"]) * ratio)) if node_box else 0
                ),
                "node_height_px": (
                    int(round(float(node_box["height"]) * ratio)) if node_box else 0
                ),
                "capture_backend": "playwright-page-screenshot",
            }
            return {
                "ok": True,
                "png": bytes(png),
                "metadata": metadata,
            }
        finally:
            if browser is not None:
                await browser.close()


SCREENSHOT_BROKER = ScreenshotBroker()
