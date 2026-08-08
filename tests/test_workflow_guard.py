import unittest

from comfy_pi_agent.workflow_guard import (
    MIN_NODE_GAP,
    V2_RENDERER,
    finalize_generated_workflow,
    validate_generated_workflow,
)


class SourceNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}
    RETURN_TYPES = ("IMAGE",)


class ProcessorNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}
    RETURN_TYPES = ("IMAGE",)


class SaveNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",)}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True


REGISTRY = {"Source": SourceNode, "Processor": ProcessorNode, "Save": SaveNode}


def ui_workflow():
    return {
        "last_node_id": 3, "last_link_id": 2,
        "nodes": [
            {"id": 1, "type": "Source", "pos": [0, 0], "size": [200, 100],
             "flags": {}, "order": 0, "mode": 0, "inputs": [],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}], "properties": {}},
            {"id": 2, "type": "Processor", "pos": [0, 0], "size": [200, 100],
             "flags": {}, "order": 1, "mode": 0,
             "inputs": [{"name": "image", "type": "IMAGE", "link": 1}],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}], "properties": {}},
            {"id": 3, "type": "Save", "pos": [0, 0], "size": [200, 100],
             "flags": {}, "order": 2, "mode": 0,
             "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
             "outputs": [], "properties": {}},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"], [2, 2, 0, 3, 0, "IMAGE"]],
        "groups": [], "config": {}, "extra": {}, "version": 0.4,
    }


class WorkflowGenerationGateTests(unittest.TestCase):
    def test_finalizer_uses_nodes_v2_and_separates_every_node(self):
        result = finalize_generated_workflow(ui_workflow(), live_registry=REGISTRY)
        self.assertTrue(result["valid"])
        self.assertTrue(result["runnable_candidate"])
        self.assertEqual(result["workflow"]["extra"]["workflowRendererVersion"], V2_RENDERER)
        nodes = result["workflow"]["nodes"]
        for index, a in enumerate(nodes):
            ax, ay = a["pos"]; aw, ah = a["size"]
            for b in nodes[index + 1:]:
                bx, by = b["pos"]; bw, bh = b["size"]
                self.assertTrue(
                    ax + aw + MIN_NODE_GAP <= bx or bx + bw + MIN_NODE_GAP <= ax
                    or ay + ah + MIN_NODE_GAP <= by or by + bh + MIN_NODE_GAP <= ay
                )

    def test_missing_current_instance_node_is_rejected(self):
        graph = ui_workflow()
        graph["nodes"][1]["type"] = "InventedNode"
        result = finalize_generated_workflow(graph, live_registry=REGISTRY)
        self.assertFalse(result["valid"])
        self.assertTrue(any(issue["code"] == "missing_live_node" for issue in result["issues"]))

    def test_wrong_socket_type_is_rejected(self):
        graph = ui_workflow()
        graph["nodes"][1]["inputs"][0]["type"] = "LATENT"
        graph["links"][0][5] = "LATENT"
        result = finalize_generated_workflow(graph, live_registry=REGISTRY)
        self.assertFalse(result["valid"])
        self.assertTrue(any(issue["code"] in {"serialized_type_mismatch", "live_target_type_mismatch"} for issue in result["issues"]))

    def test_missing_link_backreference_is_rejected(self):
        graph = ui_workflow()
        graph["nodes"][1]["inputs"][0]["link"] = 999
        result = finalize_generated_workflow(graph, live_registry=REGISTRY)
        self.assertFalse(result["valid"])
        self.assertTrue(any(issue["code"] == "target_link_backref_mismatch" for issue in result["issues"]))

    def test_layout_validation_enforces_six_pixels_without_relayout(self):
        graph = ui_workflow()
        graph["nodes"][0]["pos"] = [0, 0]
        graph["nodes"][1]["pos"] = [205, 0]
        graph["nodes"][2]["pos"] = [500, 0]
        graph["extra"]["workflowRendererVersion"] = V2_RENDERER
        result = validate_generated_workflow(graph, live_registry=REGISTRY, minimum_gap=6)
        self.assertFalse(result["valid"])
        self.assertTrue(any(issue["code"] == "node_gap_violation" for issue in result["issues"]))

    def test_api_prompt_requires_real_nodes_correct_types_and_output(self):
        prompt = {
            "1": {"class_type": "Source", "inputs": {}},
            "2": {"class_type": "Processor", "inputs": {"image": ["1", 0]}},
            "3": {"class_type": "Save", "inputs": {"images": ["2", 0]}},
        }
        result = finalize_generated_workflow(prompt, live_registry=REGISTRY)
        self.assertTrue(result["valid"])
        self.assertTrue(result["has_output_node"])

    def test_api_prompt_rejects_missing_required_input(self):
        prompt = {"1": {"class_type": "Source", "inputs": {}}, "2": {"class_type": "Save", "inputs": {}}}
        result = finalize_generated_workflow(prompt, live_registry=REGISTRY)
        self.assertFalse(result["valid"])
        self.assertTrue(any(issue["code"] == "missing_required_input" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
