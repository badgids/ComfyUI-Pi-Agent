import json
import tempfile
import unittest
from pathlib import Path

from comfy_pi_agent.nle import create_kdenlive_package
from comfy_pi_agent.tutorials import compile_tutorial, load_tutorial, select_stage


WORKFLOW = {
    "last_node_id": 1,
    "last_link_id": 0,
    "nodes": [
        {"id": 1, "type": "PiShowText", "pos": [0, 0], "size": [300, 120], "flags": {}, "order": 0, "mode": 0,
         "inputs": [], "outputs": [{"name": "text", "type": "STRING", "links": None, "slot_index": 0}], "properties": {}, "widgets_values": ["hello"]}
    ],
    "links": [], "groups": [], "config": {}, "extra": {}, "version": 0.4
}


class TutorialNleTests(unittest.TestCase):
    def test_compile_tutorial(self):
        with tempfile.TemporaryDirectory() as temp:
            result = compile_tutorial([{"name": "hello", "workflow": WORKFLOW}], "Test Tutorial", temp)
            root = Path(result["tutorial_directory"])
            self.assertTrue((root / "COMPLETE_TUTORIAL.docx").is_file())
            self.assertTrue((root / "02_CONTROLLER" / "Tutorial_Controller.json").is_file())
            tutorial = load_tutorial(str(root))
            self.assertEqual(tutorial["interface"], "comfyui_native")
            self.assertEqual(select_stage(tutorial, 1)["stage_id"], "stage-01")
            annotated = json.loads((root / "03_STAGES" / "STAGE_01" / "workflow_tutorial.json").read_text())
            self.assertGreater(len(annotated["nodes"]), len(WORKFLOW["nodes"]))

    def test_kdenlive_package(self):
        manifest = {
            "title": "Test Film",
            "profile": {"frame_rate": "24/1"},
            "shots": [{"shot_id": "1-01", "duration": 2.0, "media_path": "clip.mp4"}]
        }
        with tempfile.TemporaryDirectory() as temp:
            result = create_kdenlive_package(manifest, temp)
            self.assertTrue(Path(result["kdenlive_project"]).is_file())
            self.assertEqual(result["missing_clips"], 0)


if __name__ == "__main__":
    unittest.main()
