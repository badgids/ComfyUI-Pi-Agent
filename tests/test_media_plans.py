import unittest

from comfy_pi_agent.media_plans import (
    create_audio_workflow_plan,
    create_build_plan,
    create_character_sheet_plan,
    create_image_workflow_plan,
    create_moodboard_plan,
    create_storyboard_plan,
)


class MediaPlanTests(unittest.TestCase):
    def test_qwen_edit_plan_warns_without_reference(self):
        plan = create_image_workflow_plan("Change the coat.", "qwen-image-edit", "image_edit", "[]", "gguf")
        self.assertEqual(plan["model_family"], "qwen-image-edit")
        self.assertGreaterEqual(len(plan["warnings"]), 2)

    def test_audio_reference_warning(self):
        plan = create_audio_workflow_plan("Clone this voice.", "qwen3-tts", "voice_clone")
        self.assertTrue(plan["warnings"])

    def test_character_plan(self):
        plan = create_character_sheet_plan("A pony", "front, rear", "happy", "rain coat", "qwen-image-edit")
        self.assertEqual(plan["views"], ["front", "rear"])

    def test_moodboard(self):
        board = create_moodboard_plan("Workshop", "dark and practical", "lighting, materials", "[]")
        self.assertIn("lighting", board["categories"])

    def test_storyboard(self):
        board = create_storyboard_plan({"shots": [{"shot_id": "1-01", "scene_id": "scene-001"}]})
        self.assertEqual(len(board["panels"]), 1)

    def test_build_plan(self):
        plan = create_build_plan({"stages": [{"stage_id": "01", "status": "approved"}]}, "incremental", "complete", "project", "")
        self.assertEqual(plan["actions"][0]["action"], "preserve")


if __name__ == "__main__":
    unittest.main()
