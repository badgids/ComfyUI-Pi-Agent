import unittest

from comfy_pi_agent.mcp.graph_patch import compile_graph_patch, workflow_graph_hash
from comfy_pi_agent.mcp.node_catalog import catalog_contract_hash

CATALOG = {
    "Source": {"display_name": "Source", "input": {}, "output": ["IMAGE"], "output_name": ["IMAGE"]},
    "Sink": {
        "display_name": "Image Sink",
        "input": {"required": {"images": ["IMAGE", {}], "prefix": [["a", "b"], {"default": "a"}]}},
        "output": [],
    },
    "OtherSink": {"display_name": "Image Sink", "input": {"required": {"images": ["IMAGE", {}]}}, "output": []},
}
WORKFLOW = {"nodes": [], "links": [], "groups": [], "version": 0.4}


class GraphPatchTests(unittest.TestCase):
    def test_compiles_schema_pinned_exact_edge(self):
        result = compile_graph_patch(
            {
                "application_id": "test-application-0001",
                "nodes": [
                    {"alias": "source", "node_type": "Source"},
                    {"alias": "sink", "node_type": "Sink"},
                ],
                "connections": [
                    {"source": "source", "target": "sink", "output": "IMAGE", "input": "images"}
                ],
            },
            WORKFLOW,
            CATALOG,
            workflow_identity="wf-1",
        )
        self.assertTrue(result["valid"])
        req = result["apply_request"]
        self.assertEqual(req["expected_catalog_hash"], catalog_contract_hash(CATALOG))
        self.assertEqual(req["plan"]["expected_graph_hash"], workflow_graph_hash(WORKFLOW))
        edge = req["plan"]["add_edges"][0]
        self.assertEqual(edge["target"]["socket_index"], 0)
        self.assertEqual(edge["source"]["node_type"], "Source")
        self.assertEqual(edge["target"]["node_type"], "Sink")
        self.assertTrue(edge["source"]["schema_hash"])
        self.assertTrue(req["plan"]["create_nodes"][0]["schema_hash"])

    def test_ambiguous_semantic_node_requires_choice(self):
        result = compile_graph_patch({"nodes": [{"alias": "sink", "role": "Image Sink"}]}, WORKFLOW, CATALOG)
        self.assertFalse(result["valid"])
        self.assertTrue(result["needs_choice"])
        self.assertGreaterEqual(len(result["choices"]), 2)

    def test_incompatible_edge_fails_when_converter_inference_disabled(self):
        catalog = dict(CATALOG)
        catalog["Bad"] = {"display_name": "Bad", "input": {"required": {"model": ["MODEL", {}]}}, "output": []}
        result = compile_graph_patch(
            {
                "allow_inferred_converters": False,
                "nodes": [{"alias": "source", "node_type": "Source"}, {"alias": "bad", "node_type": "Bad"}],
                "connections": [{"source": "source", "target": "bad", "output": "IMAGE", "input": "model"}],
            },
            WORKFLOW,
            catalog,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["issues"][0]["code"], "invalid_edge")

    def test_unique_safe_converter_is_inferred_but_ambiguous_routes_require_choice(self):
        catalog = {
            "Source": CATALOG["Source"],
            "LatentSink": {"display_name": "Latent Sink", "input": {"required": {"latent": ["LATENT", {}]}}, "output": []},
            "ImageToLatent": {"display_name": "Image To Latent", "input": {"required": {"image": ["IMAGE", {}]}}, "output": ["LATENT"], "output_name": ["LATENT"]},
        }
        request = {
            "nodes": [{"alias": "source", "node_type": "Source"}, {"alias": "sink", "node_type": "LatentSink"}],
            "connections": [{"source": "source", "target": "sink", "output": "IMAGE", "input": "latent"}],
        }
        result = compile_graph_patch(request, WORKFLOW, catalog)
        self.assertTrue(result["valid"])
        self.assertEqual([item["node_type"] for item in result["plan"]["create_nodes"]], ["Source", "LatentSink", "ImageToLatent"])
        self.assertEqual(len(result["plan"]["add_edges"]), 2)
        self.assertTrue(all(edge["inferred"] for edge in result["plan"]["add_edges"]))

        catalog["ImageToLatentAlternative"] = {
            "display_name": "Alternative Converter",
            "input": {"required": {"image": ["IMAGE", {}]}},
            "output": ["LATENT"],
            "output_name": ["LATENT"],
        }
        choice = compile_graph_patch(request, WORKFLOW, catalog)
        self.assertFalse(choice["valid"])
        self.assertTrue(choice["needs_choice"])
        self.assertEqual(set(choice["choices"]), {"ImageToLatent", "ImageToLatentAlternative"})

    def test_selected_existing_node_selector_is_exact_and_values_use_live_choices(self):
        workflow = {
            "nodes": [{"id": 7, "type": "Sink", "title": "Target", "pos": [0, 0], "size": [200, 100]}],
            "links": [],
            "groups": [],
            "version": 0.4,
        }
        result = compile_graph_patch(
            {"updates": [{"selector": {"selected": True}, "values": {"prefix": "b"}}]},
            workflow,
            CATALOG,
            selected_node_ids=[7],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["plan"]["update_nodes"][0]["ref"], {"node_id": "7"})
        invalid = compile_graph_patch(
            {"updates": [{"selector": {"selected": True}, "values": {"prefix": "not-live"}}]},
            workflow,
            CATALOG,
            selected_node_ids=[7],
        )
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["issues"][0]["code"], "invalid_value")


if __name__ == "__main__":
    unittest.main()
