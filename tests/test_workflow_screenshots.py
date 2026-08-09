import asyncio
import unittest
from pathlib import Path

from comfy_pi_agent.agent_guidance import select_skills
from comfy_pi_agent.workflow_screenshots import (
    EXACT_NODE_SCREENSHOT_MODE,
    MIN_NODE_SCREENSHOT_PADDING,
    ScreenshotBroker,
    _box_clip,
    _required_node_viewport,
)


ROOT = Path(__file__).resolve().parents[1]


class ScreenshotBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_node_request_clamps_padding_to_300_and_returns_png(self):
        broker = ScreenshotBroker()
        waiter = asyncio.create_task(
            broker.request(
                {"mode": "node", "node_id": "17", "padding_px": 12, "pixel_ratio": 1.5},
                timeout=2,
            )
        )
        await asyncio.sleep(0)
        claimed = broker.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["mode"], "node")
        self.assertEqual(claimed["node_id"], "17")
        self.assertEqual(claimed["padding_px"], MIN_NODE_SCREENSHOT_PADDING)
        self.assertTrue(
            broker.complete(
                claimed["request_id"],
                b"\x89PNG\r\n\x1a\npayload",
                {"width": "1200", "height": "900", "padding_px": "300"},
            )
        )
        result = await waiter
        self.assertTrue(result["ok"])
        self.assertTrue(result["png"].startswith(b"\x89PNG"))
        self.assertEqual(result["metadata"]["padding_px"], "300")

    async def test_invalid_node_request_fails_before_browser_claim(self):
        broker = ScreenshotBroker()
        with self.assertRaises(ValueError):
            await broker.request({"mode": "node", "node_id": ""}, timeout=1)

    async def test_exact_node_request_forces_zero_padding_and_preserves_override(self):
        broker = ScreenshotBroker()
        workflow = {"nodes": [{"id": 7, "type": "KSampler"}], "links": []}
        waiter = asyncio.create_task(
            broker.request(
                {
                    "mode": EXACT_NODE_SCREENSHOT_MODE,
                    "node_type": "KSampler",
                    "workflow": workflow,
                    "padding_px": 999,
                },
                timeout=2,
            )
        )
        await asyncio.sleep(0)
        claimed = broker.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["mode"], EXACT_NODE_SCREENSHOT_MODE)
        self.assertEqual(claimed["node_type"], "KSampler")
        self.assertEqual(claimed["padding_px"], 0)
        self.assertEqual(claimed["workflow"], workflow)
        self.assertTrue(
            broker.complete(
                claimed["request_id"],
                b"\x89PNG\r\n\x1a\npayload",
                {
                    "width": "420",
                    "height": "260",
                    "padding_px": "0",
                    "node_width_px": "420",
                    "node_height_px": "260",
                    "node_type": "KSampler",
                    "capture_backend": "playwright-page-screenshot",
                },
            )
        )
        result = await waiter
        self.assertTrue(result["ok"])
        self.assertEqual(result["metadata"]["padding_px"], "0")

    async def test_exact_node_request_requires_id_or_type(self):
        broker = ScreenshotBroker()
        with self.assertRaises(ValueError):
            await broker.request({"mode": EXACT_NODE_SCREENSHOT_MODE}, timeout=1)


class ScreenshotGeometryTests(unittest.TestCase):
    def test_node_clip_adds_300_css_pixels_on_every_side(self):
        clip = _box_clip({"x": 500, "y": 650, "width": 240, "height": 180}, 300)
        self.assertEqual(clip["x"], 200)
        self.assertEqual(clip["y"], 350)
        self.assertEqual(clip["width"], 840)
        self.assertEqual(clip["height"], 780)

    def test_large_node_forces_viewport_large_enough_for_margin(self):
        viewport = _required_node_viewport(
            {"x": 0, "y": 0, "width": 882, "height": 1077},
            300,
            {"width": 1200, "height": 900},
        )
        self.assertGreaterEqual(viewport["width"], 882 + 600)
        self.assertGreaterEqual(viewport["height"], 1077 + 600)

    def test_exact_node_clip_uses_measured_dom_box_without_context_padding(self):
        box = {"x": 500, "y": 650, "width": 240, "height": 180}
        self.assertEqual(_box_clip(box, 0), {
            "x": 500.0, "y": 650.0, "width": 240.0, "height": 180.0
        })
        viewport = _required_node_viewport(
            box,
            0,
            {"width": 800, "height": 600},
            minimum_padding=0,
        )
        self.assertGreaterEqual(viewport["width"], 240 + 160)
        self.assertGreaterEqual(viewport["height"], 180 + 160)


class ScreenshotArchitectureTests(unittest.TestCase):
    def test_active_browser_supplies_workflow_but_playwright_owns_png_capture(self):
        js = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn("currentWorkflow()", js)
        self.assertIn("app.loadGraphData(workflow, true, false, null", js)
        self.assertIn("skipAssetScans: true", js)
        self.assertIn("__COMFYUI_PI_PREPARE_PLAYWRIGHT_CAPTURE__", js)
        self.assertIn("__COMFYUI_PI_PLAYWRIGHT_CAPTURE_READY__", js)
        self.assertIn("installPlaywrightCaptureBridge()", js)
        setup_source = js[js.index("  async setup() {"):]
        self.assertIn("installPlaywrightCaptureBridge()", setup_source)
        self.assertIn('"/pi-agent/screenshot/playwright"', js)
        self.assertIn("comfyui_pi_playwright_capture", js)
        self.assertIn("SCREENSHOT_MIN_NODE_PADDING = 300", js)
        self.assertIn('SCREENSHOT_EXACT_NODE_MODE = "node_exact"', js)
        self.assertIn("screenshotInstalledNodeWorkflow", js)
        self.assertNotIn("screenshotNodeForeignObject", js)
        self.assertNotIn("screenshotRenderGraphRegion", js)
        self.assertNotIn("XMLSerializer", js)
        self.assertNotIn("html2canvas", js)

    def test_python_backend_uses_real_playwright_clip_screenshot_and_vue_node_box(self):
        source = (ROOT / "comfy_pi_agent" / "workflow_screenshots.py").read_text(encoding="utf-8")
        self.assertIn("from playwright.async_api import async_playwright", source)
        self.assertIn("page.screenshot(", source)
        self.assertIn("clip=clip", source)
        self.assertIn("_stable_locator_box", source)
        self.assertIn('page.wait_for_selector(".lg-node[data-node-id]"', source)
        self.assertIn('page.locator(".lg-node[data-node-id]")', source)
        self.assertIn('return f\'.lg-node[data-node-id="{escaped}"]\'', source)
        self.assertNotIn('], [data-node-id=', source)
        self.assertIn('prepared.get("workflow_box")', source)
        self.assertIn("capture_backend", source)

    def test_playwright_route_and_optional_dependency_are_declared(self):
        routes = (ROOT / "comfy_pi_agent" / "routes.py").read_text(encoding="utf-8")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('@routes.post("/pi-agent/screenshot/playwright")', routes)
        self.assertIn("capture_with_playwright", routes)
        self.assertIn("screenshots = [", pyproject)
        self.assertIn('"playwright>=1.50,<2"', pyproject)

    def test_terminal_tool_enforces_minimum_300_node_padding_and_markdown(self):
        text = (ROOT / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn('name: "comfyui_workflow_screenshot"', text)
        self.assertIn("Math.max(300, requestedPadding)", text)
        self.assertIn("/pi-agent/screenshot/request", text)
        self.assertIn("upsertScreenshotMarkdown", text)
        self.assertIn("Buffer.from(await response.arrayBuffer())", text)
        self.assertIn("minimum 300px", text)

    def test_markdown_node_image_uses_exact_real_frontend_capture(self):
        bridge = (ROOT / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn('name: "comfyui_markdown_node_image"', bridge)
        self.assertIn('mode: "node_exact"', bridge)
        self.assertIn('renderer: "real-comfyui-playwright-png"', bridge)
        self.assertIn('captureBackend !== "playwright-page-screenshot"', bridge)
        self.assertNotIn('runMarkdownDiagramCli("node"', bridge)

    def test_screenshot_requests_route_to_document_export_skill(self):
        matches = select_skills("Take a close-up screenshot of node 24 for this Markdown tutorial")
        self.assertIn("document-export", [item.name for item in matches])


if __name__ == "__main__":
    unittest.main()
