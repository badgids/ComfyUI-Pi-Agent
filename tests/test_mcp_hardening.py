import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.mcp.families.graph import _record_verified_edges
from comfy_pi_agent.mcp.families.web import _safe_public
from comfy_pi_agent.mcp.node_catalog import NodeCatalogStore

ROOT = Path(__file__).resolve().parents[1]


class McpHardeningTests(unittest.TestCase):
    def test_web_fetch_rejects_loopback_and_validates_redirect_before_request(self):
        with self.assertRaises(ValueError):
            _safe_public("http://127.0.0.1/private")
        source = (ROOT / "comfy_pi_agent" / "mcp" / "families" / "web.py").read_text(encoding="utf-8")
        self.assertIn("class _SafeRedirectHandler", source)
        self.assertIn("_safe_public(target)", source)
        self.assertIn("build_opener(_SafeRedirectHandler())", source)

    def test_custom_node_patch_checks_before_apply_and_commit_stages_explicitly(self):
        source = (ROOT / "comfy_pi_agent" / "mcp" / "families" / "custom_nodes.py").read_text(encoding="utf-8")
        self.assertIn('["git","apply","--check","--whitespace=error-all","-"]', source)
        self.assertIn('["git","add","-A","--"]', source)
        self.assertNotIn('"commit","-am"', source)

    def test_only_successfully_verified_edges_become_schema_scoped_lessons(self):
        request = {
            "application_id": "lesson-test-0001",
            "plan": {
                "add_edges": [{
                    "source": {"node_type": "Source", "schema_hash": "a" * 64, "name": "IMAGE", "output_index": 0, "type": "IMAGE"},
                    "target": {"node_type": "Sink", "schema_hash": "b" * 64, "name": "images", "input_index": 0, "socket_index": 0, "type": "IMAGE"},
                }]
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = NodeCatalogStore(Path(tmp) / "catalog.sqlite3")
            with patch("comfy_pi_agent.mcp.families.graph.NodeCatalogStore", return_value=store):
                _record_verified_edges(request, {"success": True, "verification": {"valid": True}})
            reopened = NodeCatalogStore(Path(tmp) / "catalog.sqlite3")
            lessons = reopened.lessons("Source", "a" * 64)
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0]["payload"]["target_node_type"], "Sink")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
