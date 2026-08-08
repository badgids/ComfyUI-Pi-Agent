import asyncio
import unittest
from pathlib import Path

from comfy_pi_agent.agent_guidance import select_skills
from comfy_pi_agent.workflow_screenshots import (
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


class ScreenshotArchitectureTests(unittest.TestCase):
    def test_active_browser_supplies_workflow_but_playwright_owns_png_capture(self):
        js = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn("currentWorkflow()", js)
        self.assertIn("app.loadGraphData(workflow)", js)
        self.assertIn("__COMFYUI_PI_PREPARE_PLAYWRIGHT_CAPTURE__", js)
        self.assertIn('"/pi-agent/screenshot/playwright"', js)
        self.assertIn("comfyui_pi_playwright_capture", js)
        self.assertIn("SCREENSHOT_MIN_NODE_PADDING = 300", js)
        self.assertNotIn("screenshotNodeForeignObject", js)
        self.assertNotIn("screenshotRenderGraphRegion", js)
        self.assertNotIn("XMLSerializer", js)
        self.assertNotIn("html2canvas", js)

    def test_python_backend_uses_real_playwright_clip_screenshot_and_vue_node_box(self):
        source = (ROOT / "comfy_pi_agent" / "workflow_screenshots.py").read_text(encoding="utf-8")
        self.assertIn("from playwright.async_api import async_playwright", source)
        self.assertIn("page.screenshot(", source)
        self.assertIn("clip=clip", source)
        self.assertIn("await locator.bounding_box()", source)
        self.assertIn(".lg-node[data-node-id=", source)
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

    def test_screenshot_requests_route_to_document_export_skill(self):
        matches = select_skills("Take a close-up screenshot of node 24 for this Markdown tutorial")
        self.assertIn("document-export", [item.name for item in matches])


if __name__ == "__main__":
    unittest.main()
