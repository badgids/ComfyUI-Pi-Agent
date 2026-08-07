import json
import unittest

from comfy_pi_agent.workflow import analyze_workflow, repair_workflow, validate_workflow


class WorkflowTests(unittest.TestCase):
    def test_analyze_api_workflow(self):
        workflow = {
            "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}}
        }
        report = analyze_workflow(workflow, live_registry={"LoadImage": object, "SaveImage": object})
        self.assertEqual(report.format, "api")
        self.assertEqual(report.node_count, 2)
        self.assertEqual(report.link_count, 1)
        self.assertIn("input.png", report.input_files)

    def test_validate_unknown(self):
        result = validate_workflow({"hello": "world"})
        self.assertFalse(result["valid"])

    def test_repair_inputs(self):
        result = repair_workflow({"1": {"class_type": "Example", "inputs": []}})
        self.assertTrue(result["changed"])
        self.assertEqual(result["repaired"]["1"]["inputs"], {})


if __name__ == "__main__":
    unittest.main()
