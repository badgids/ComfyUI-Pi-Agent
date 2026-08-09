import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class DynamicMcpIntegrationTests(unittest.TestCase):
    def test_plugin_registers_optional_mcp_routes_without_making_core_depend_on_them(self):
        source=(ROOT/"__init__.py").read_text(encoding="utf-8")
        self.assertIn("register_mcp_routes",source)
        self.assertIn("Pi Agent MCP routes were not registered",source)
        self.assertGreater(source.index("from .comfy_pi_agent.mcp.routes"), source.index("register_routes()"))

    def test_both_pi_modes_load_dynamic_tool_extension_explicitly(self):
        runtime=(ROOT/"comfy_pi_agent"/"pi_runtime.py").read_text(encoding="utf-8")
        terminal=(ROOT/"pi"/"terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn("_DYNAMIC_MCP_EXTENSION",runtime)
        self.assertIn('"-e", str(_DYNAMIC_MCP_EXTENSION)',runtime)
        self.assertIn("COMFYUI_PI_MCP_RUNTIME_FILE",runtime)
        self.assertIn('from "./dynamic-mcp-tools"',terminal)
        self.assertIn("registerDynamicMcpTools(pi)",terminal)

if __name__=="__main__": unittest.main()
