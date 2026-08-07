import unittest

from comfy_pi_agent.nodes import NODE_CLASS_MAPPINGS


class NodeRegistrationTests(unittest.TestCase):
    def test_core_nodes_registered(self):
        expected = {
            "PiAgentStatus", "PiAgentPrompt", "PiWorkflowAnalyze", "PiModelInventory",
            "PiProjectCompile", "PiTutorialCompile", "PiKdenlivePackage", "PiDocxExport"
        }
        self.assertTrue(expected.issubset(NODE_CLASS_MAPPINGS))

    def test_input_types(self):
        for name, node_class in NODE_CLASS_MAPPINGS.items():
            self.assertTrue(callable(getattr(node_class, "INPUT_TYPES", None)), name)
            self.assertTrue(hasattr(node_class, "RETURN_TYPES"), name)


    def test_dynamic_context_router_reports_task_procedures(self):
        node = NODE_CLASS_MAPPINGS["PiIntegrationContextRouter"]()
        routing_json, preview = node.run("Repair this workflow", '{"nodes": [], "links": []}', True)
        self.assertIn("workflow-intelligence", routing_json)
        self.assertIn("workflow-intelligence", preview)

    def test_agent_prompt_accepts_optional_workflow_context(self):
        inputs = NODE_CLASS_MAPPINGS["PiAgentPrompt"].INPUT_TYPES()
        self.assertIn("workflow_json_or_path", inputs.get("optional", {}))


if __name__ == "__main__":
    unittest.main()
