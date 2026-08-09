import unittest
from unittest.mock import patch
from comfy_pi_agent.mcp.server import DynamicMcpServer

class DynamicMcpServerTests(unittest.TestCase):
    def test_tool_list_starts_small_and_emits_list_changed(self):
        sent=[]; server=DynamicMcpServer(send=sent.append)
        names={tool["name"] for tool in server.list_tools()}
        self.assertIn("comfyui_tool_search", names)
        self.assertIn("mcp_capability_audit", names)
        self.assertNotIn("custom_nodes_git_push", names)
        server.activate(["custom_nodes_git_push"])
        self.assertFalse(any(item.get("method")=="notifications/tools/list_changed" for item in sent))
        self.assertNotIn("custom_nodes_git_push", {tool["name"] for tool in server.list_tools()})
        server.handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}})
        server.activate(["custom_nodes_git_commit"])
        self.assertTrue(any(item.get("method")=="notifications/tools/list_changed" for item in sent))
        self.assertIn("custom_nodes_git_commit", {tool["name"] for tool in server.list_tools()})

    @patch("comfy_pi_agent.mcp.server.invoke_remote", return_value={"ok": True})
    def test_hidden_exact_tool_autoactivates_on_direct_call(self, invoke):
        sent=[]; server=DynamicMcpServer(send=sent.append)
        result=server.call("node_library_search", {"query":"sampler"})
        self.assertEqual(result, {"ok":True})
        self.assertIn("node_library_search", server.active)
        invoke.assert_called_once()

if __name__ == "__main__": unittest.main()
