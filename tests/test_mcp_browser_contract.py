import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BrowserContractTests(unittest.TestCase):
    def test_browser_bridge_is_transactional_and_real_screenshot_only(self):
        source = (ROOT / "web" / "mcp_bridge.js").read_text(encoding="utf-8")
        for token in (
            "workflow_identity_precondition_failed",
            "graph_precondition_failed",
            "concurrent_workflow_edit",
            "canvas_mutation_busy",
            "canvas.read_only = true",
            "assertMutationGuard",
            "acceptMutationGuard",
            "patchLedger",
            "app.loadGraphData(structuredClone(before)",
            "rollback.hash_verified",
            "unrelated_node_changed",
            "workflow_envelope_changed",
            "removed_edge_still_present",
            "real_screenshot_failed",
        ):
            self.assertIn(token, source)
        self.assertIn('apply_workflow_graph_patch: 3', source)
        self.assertIn('name: "ComfyUI.PiAgent.MCPBridge"', source)
        self.assertIn('apply_workflow_graph_patch: applyGraphPatch', source)
        self.assertNotIn("canvas.toBlob", source)
        self.assertNotRegex(source, r"\$\{[^}]+![rsa]\}")

    def test_pi_extension_routes_before_turn_and_keeps_meta_tools(self):
        source = (ROOT / "pi" / "dynamic-mcp-tools.ts").read_text(encoding="utf-8")
        self.assertIn('name: "comfyui_tool_search"', source)
        self.assertIn('name: "comfyui_tool_activate"', source)
        self.assertIn('name: "comfyui_tool_call"', source)
        self.assertIn('pi.on("input"', source)
        self.assertIn('"route-text"', source)
        self.assertIn("MAX_DYNAMIC_TOOLS = 48", source)
        self.assertIn("schemaToTypeBox", source)


if __name__ == "__main__":
    unittest.main()
