import asyncio
import unittest
from pathlib import Path

from comfy_pi_agent.agent_guidance import select_skills
from comfy_pi_agent.workflow_screenshots import (
    MIN_NODE_SCREENSHOT_PADDING,
    ScreenshotBroker,
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


class ScreenshotArchitectureTests(unittest.TestCase):
    def test_browser_captures_real_v2_nodes_and_restores_view(self):
        text = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn('document.getElementById("graph-canvas")', text)
        self.assertIn('document.querySelectorAll("[data-node-id]")', text)
        self.assertIn("SCREENSHOT_MIN_NODE_PADDING = 300", text)
        self.assertIn("screenshotSaveView", text)
        self.assertIn("screenshotRestoreView", text)
        self.assertIn("screenshotFitBounds", text)
        self.assertIn("screenshotNodeForeignObject", text)
        self.assertIn("screenshotGraphCanvasLayers", text)
        self.assertIn('"/pi-agent/screenshot/pending"', text)
        self.assertIn("startWorkflowScreenshotWorker();", text)
        self.assertNotIn("html2canvas", text)

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
