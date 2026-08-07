import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.integrations.router import (
    build_dynamic_integration_context,
    integration_status,
    match_integrations,
)
from comfy_pi_agent.integrations.minimax_h3_director import (
    DIRECTOR_NODE_IDS,
    create_minimax_h3_director_workflow,
    detect_minimax_h3_director,
    inspect_minimax_h3_director_workflow,
)
from comfy_pi_agent.integrations.whatdreamscost import (
    WDC_NODE_IDS,
    create_whatdreamscost_plan,
    create_whatdreamscost_workflow,
    find_whatdreamscost_install,
    inspect_whatdreamscost_workflow,
)
from comfy_pi_agent.integrations.scene_camera_action import (
    SCA_NODE_IDS,
    create_scene_camera_action_plan,
    create_scene_camera_action_workflow,
    inspect_scene_camera_action_workflow,
    inspect_scene_state,
)
from comfy_pi_agent.integrations.minimax_h3_turbo import (
    TURBO_NODE_IDS,
    create_minimax_h3_turbo_plan,
    create_minimax_h3_turbo_workflow,
    inspect_minimax_h3_turbo_workflow,
)
from comfy_pi_agent.workflow import analyze_workflow
from comfy_pi_agent.nodes import NODE_CLASS_MAPPINGS


class IntegrationRoutingTests(unittest.TestCase):
    def test_node_import_does_not_eager_load_integration_modules(self):
        code = (
            "import sys; import comfy_pi_agent.nodes; import comfy_pi_agent.routes; "
            "mods=['comfy_pi_agent.integrations.minimax_h3_director','comfy_pi_agent.integrations.whatdreamscost',"
            "'comfy_pi_agent.integrations.scene_camera_action','comfy_pi_agent.integrations.minimax_h3_turbo']; "
            "print(' '.join(str(int(m in sys.modules)) for m in mods))"
        )
        output = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
        self.assertEqual(output, "0 0 0 0")

    def test_unrelated_request_loads_no_node_pack_context(self):
        result = build_dynamic_integration_context(message="Write a short story about a bicycle.")
        self.assertEqual(result["loaded_integrations"], [])
        self.assertEqual(result["context"], "")
        self.assertFalse(result["startup_injection"])

    def test_minimax_request_loads_only_minimax(self):
        result = build_dynamic_integration_context(message="Create a MiniMax H3 Director ref2VA workflow")
        ids = [item["id"] for item in result["loaded_integrations"]]
        self.assertEqual(ids, ["minimax-h3-director"])
        self.assertIn("MiniMax H3 Director", result["context"])

    def test_whatdreamscost_request_loads_only_wdc(self):
        result = build_dynamic_integration_context(message="Explain the LTX Director Prompt Relay workflow")
        ids = [item["id"] for item in result["loaded_integrations"]]
        self.assertEqual(ids, ["whatdreamscost-comfyui"])
        self.assertIn("WhatDreamsCost", result["context"])
        self.assertIn("timeline_data", result["context"])

    def test_normal_match_uses_compact_context_not_full_skill(self):
        result = build_dynamic_integration_context(message="Explain WhatDreamsCost Multi Image Loader")
        self.assertLess(result["context_chars"], 5000)
        self.assertFalse(result["loaded_integrations"][0]["full_skill_loaded"])
        self.assertIn("gallery-style image loader", result["context"])
        self.assertNotIn("## Workflow repair policy", result["context"])

    def test_explicit_comprehensive_tutorial_can_load_full_skill(self):
        result = build_dynamic_integration_context(message="Create a comprehensive tutorial for LTX Director")
        self.assertTrue(result["loaded_integrations"][0]["full_skill_loaded"])
        self.assertIn("## Workflow creation policy", result["context"])

    def test_workflow_node_detection(self):
        workflow = {"nodes": [{"id": 1, "type": "LTXDirector", "widgets_values": []}], "links": []}
        matched = match_integrations(workflow=workflow)
        self.assertEqual([m["id"] for m in matched], ["whatdreamscost-comfyui"])

    def test_both_integrations_can_be_selected_without_global_pollution(self):
        workflow = {
            "nodes": [
                {"id": 1, "type": "LTXDirector", "widgets_values": []},
                {"id": 2, "type": "MiniMaxH3DirectorCS", "widgets_values": []},
            ],
            "links": [],
        }
        status = integration_status(workflow=workflow)
        self.assertEqual({m["id"] for m in status["matched"]}, {"minimax-h3-director", "whatdreamscost-comfyui"})


    def test_scene_camera_action_request_loads_only_scene_pack(self):
        result = build_dynamic_integration_context(message="Create a Scene Camera Action Staging 3D previz scene")
        ids = [item["id"] for item in result["loaded_integrations"]]
        self.assertEqual(ids, ["scene-camera-action"])
        self.assertIn("SceneNode", result["context"])
        self.assertLess(result["context_chars"], 6000)
        self.assertFalse(result["loaded_integrations"][0]["full_skill_loaded"])

    def test_h3_turbo_request_does_not_pull_director_context(self):
        result = build_dynamic_integration_context(message="Create a MiniMax H3 Turbo 4-step workflow")
        ids = [item["id"] for item in result["loaded_integrations"]]
        self.assertEqual(ids, ["minimax-h3-turbo"])
        self.assertIn("MiniMaxH3TurboSampler", result["context"])
        self.assertNotIn("Dynamically loaded integration knowledge: MiniMax H3 Director", result["context"])

    def test_director_detector_does_not_claim_turbo_request(self):
        self.assertFalse(detect_minimax_h3_director(message="Create a MiniMax H3 Turbo 4-step workflow"))

    def test_new_pack_nodes_route_from_workflow_without_message(self):
        workflow = {"nodes": [
            {"id": 1, "type": "SceneNode", "widgets_values": []},
            {"id": 2, "type": "MiniMaxH3TurboSampler", "widgets_values": []},
        ], "links": []}
        matched = match_integrations(workflow=workflow)
        self.assertEqual({m["id"] for m in matched}, {"scene-camera-action", "minimax-h3-turbo"})


class MiniMaxDirectorIntegrationTests(unittest.TestCase):
    def test_public_node_set_is_complete(self):
        self.assertEqual(DIRECTOR_NODE_IDS, {
            "MiniMaxH3DirectorCS", "MiniMaxH3PreviewOverrideCS",
            "MiniMaxH3RetakeStitchCS", "MiniMaxH3EnhancePromptCS",
        })

    def test_inspector_understands_reference_mode(self):
        timeline = {
            "reference_mode": "ON",
            "segments": [{"type": "text", "start": 0, "length": 120}],
            "motionSegments": [], "audioSegments": [], "characters": [],
        }
        workflow = {
            "nodes": [
                {"id": 1, "type": "MiniMaxH3DirectorCS", "properties": {"timeline_data": json.dumps(timeline)}, "widgets_values": []},
                {"id": 2, "type": "CLIPLoader", "widgets_values": ["qwen.safetensors", "minimax", "default"]},
            ],
            "links": [],
        }
        report = inspect_minimax_h3_director_workflow(workflow)
        self.assertTrue(report["detected"])
        self.assertEqual(report["details"]["director_nodes"][0]["reference_mode"], "ON")

    def test_installed_example_is_used_as_creation_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "minimax_director.py").write_text("# marker\n", encoding="utf-8")
            (root / "minimax_plan.py").write_text("# marker\n", encoding="utf-8")
            examples = root / "example_workflows"
            examples.mkdir()
            baseline = {"nodes": [{"id": 1, "type": "MiniMaxH3DirectorCS", "widgets_values": []}], "links": [], "extra": {}}
            (examples / "MiniMax H3 Director.json").write_text(json.dumps(baseline), encoding="utf-8")
            with patch.dict(os.environ, {"COMFYUI_MINIMAX_H3_DIRECTOR_PATH": str(root)}, clear=False):
                result = create_minimax_h3_director_workflow("Create a Director workflow")
            self.assertTrue(result["ok"])
            self.assertIn("MiniMax H3 Director.json", result["source_workflow"])
            self.assertEqual(result["workflow"]["extra"]["comfyui_pi_agent"]["integration"], "minimax-h3-director")



class WhatDreamsCostIntegrationTests(unittest.TestCase):
    def test_public_node_set_is_complete(self):
        expected = {
            "LTXDirector", "LTXDirectorGuide", "LTXDirectorCropGuides", "LTXKeyframer",
            "MultiImageLoader", "LTXSequencer", "SpeechLengthCalculator", "LoadAudioUI", "LoadVideoUI",
        }
        self.assertEqual(WDC_NODE_IDS, expected)

    def test_inspect_ltx_director(self):
        timeline = {"segments": [{"type": "text", "start": 0, "length": 24}], "motionSegments": [], "audioSegments": []}
        workflow = {
            "nodes": [
                {"id": 1, "type": "LTXDirector", "properties": {"timeline_data": json.dumps(timeline)}, "widgets_values": []},
                {"id": 2, "type": "CLIPLoader", "widgets_values": ["encoder.safetensors", "ltxv", "default"]},
            ],
            "links": [],
        }
        report = inspect_whatdreamscost_workflow(workflow)
        self.assertTrue(report["detected"])
        self.assertEqual(report["details"]["directors"][0]["segment_count"], 1)
        self.assertFalse(any("CLIPLoader" in warning for warning in report["warnings"]))

    def test_workflow_analyzer_attaches_wdc_report(self):
        workflow = {"nodes": [{"id": 1, "type": "LTXDirector", "widgets_values": []}], "links": []}
        report = analyze_workflow(workflow, live_registry={"LTXDirector": object()}).to_dict()
        self.assertIn("whatdreamscost-comfyui", report["integrations"])

    def test_plan_does_not_require_pack_installed(self):
        with patch.dict(os.environ, {"COMFYUI_WHATDREAMSCOST_PATH": ""}, clear=False):
            plan = create_whatdreamscost_plan("Create an LTX Director workflow", preferred_format="gguf")
        self.assertEqual(plan["integration"], "whatdreamscost-comfyui")
        self.assertEqual(plan["preferred_format"], "gguf")

    def test_installed_example_is_used_as_creation_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ltx_director.py").write_text("# marker\n", encoding="utf-8")
            (root / "prompt_relay.py").write_text("# marker\n", encoding="utf-8")
            examples = root / "example_workflows"
            examples.mkdir()
            baseline = {"nodes": [{"id": 1, "type": "LTXDirector", "widgets_values": []}], "links": [], "extra": {}}
            (examples / "LTX_Director_2_Workflow_GGUF.json").write_text(json.dumps(baseline), encoding="utf-8")
            with patch.dict(os.environ, {"COMFYUI_WHATDREAMSCOST_PATH": str(root)}, clear=False):
                status = find_whatdreamscost_install()
                result = create_whatdreamscost_workflow("Use GGUF", preferred_format="gguf")
            self.assertTrue(status["installed"])
            self.assertTrue(result["ok"])
            self.assertIn("LTX_Director_2_Workflow_GGUF.json", result["source_workflow"])
            self.assertEqual(result["workflow"]["extra"]["comfyui_pi_agent"]["integration"], "whatdreamscost-comfyui")

    def test_integration_nodes_are_registered(self):
        expected = {
            "PiIntegrationContextRouter",
            "PiWhatDreamsCostStatus", "PiWhatDreamsCostPlan", "PiWhatDreamsCostWorkflow", "PiWhatDreamsCostInspect",
            "PiMiniMaxH3DirectorStatus", "PiMiniMaxH3DirectorPlan", "PiMiniMaxH3DirectorWorkflow", "PiMiniMaxH3DirectorInspect",
            "PiSceneCameraActionStatus", "PiSceneCameraActionPlan", "PiSceneCameraActionWorkflow", "PiSceneCameraActionInspect",
            "PiMiniMaxH3TurboStatus", "PiMiniMaxH3TurboPlan", "PiMiniMaxH3TurboWorkflow", "PiMiniMaxH3TurboInspect",
        }
        self.assertTrue(expected.issubset(NODE_CLASS_MAPPINGS))


class SceneCameraActionIntegrationTests(unittest.TestCase):
    def test_public_node_set(self):
        self.assertEqual(SCA_NODE_IDS, {"SceneNode", "ActingNode", "DirectingNode"})

    def test_scene_state_validation(self):
        scene = {
            "type": "cube_scene",
            "num_assets": 1,
            "spawn_point": {"px": 0, "py": 0, "pz": 1, "ry": 0},
            "nodes": [{
                "id": "wall", "type": "block", "name": "Wall",
                "transform": {"px": 0, "py": 1.5, "pz": 0, "rx": 0, "ry": 0, "rz": 0, "sx": 4, "sy": 3, "sz": 0.25},
            }],
        }
        report = inspect_scene_state(scene)
        self.assertTrue(report["valid"])
        self.assertEqual(report["summary"]["block_count"], 1)

    def test_base_workflow_has_ordered_three_node_chain(self):
        result = create_scene_camera_action_workflow("Create warehouse previz", actor_type="car", include_directing=True)
        self.assertTrue(result["ok"])
        workflow = result["workflow"]
        self.assertEqual([n["type"] for n in workflow["nodes"]], ["SceneNode", "ActingNode", "DirectingNode"])
        report = inspect_scene_camera_action_workflow(workflow)
        self.assertTrue(report["detected"])
        self.assertFalse(any("not connected" in w for w in report["warnings"]))

    def test_plan_clamps_documented_duration(self):
        plan = create_scene_camera_action_plan("scene", duration_seconds=99)
        self.assertEqual(plan["duration_seconds"], 15.0)

    def test_workflow_analyzer_attaches_scene_report(self):
        workflow = {"nodes": [{"id": 1, "type": "SceneNode", "widgets_values": []}], "links": []}
        report = analyze_workflow(workflow, live_registry={"SceneNode": object()}).to_dict()
        self.assertIn("scene-camera-action", report["integrations"])


class MiniMaxH3TurboIntegrationTests(unittest.TestCase):
    def test_public_node_set(self):
        self.assertEqual(TURBO_NODE_IDS, {"MiniMaxH3TurboLoRA", "MiniMaxH3TurboSampler"})

    def test_inspector_requires_both_turbo_nodes(self):
        workflow = {"nodes": [{"id": 1, "type": "MiniMaxH3TurboLoRA", "widgets_values": []}], "links": []}
        report = inspect_minimax_h3_turbo_workflow(workflow)
        self.assertTrue(report["detected"])
        self.assertTrue(any("without MiniMaxH3TurboSampler" in issue for issue in report["issues"]))

    def test_plan_enforces_minimum_four_steps(self):
        plan = create_minimax_h3_turbo_plan("turbo", steps=1, low_vram=True)
        self.assertEqual(plan["steps"], 4)
        self.assertTrue(plan["low_vram"])

    def test_installed_example_is_used_as_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "__init__.py").write_text("# marker\n", encoding="utf-8")
            (root / "h3_silu_temb_grid.safetensors").write_bytes(b"marker")
            examples = root / "example_workflows"
            examples.mkdir()
            baseline = {
                "last_node_id": 3, "last_link_id": 1,
                "nodes": [
                    {"id": 1, "type": "MiniMaxH3TurboLoRA", "inputs": [], "outputs": [], "widgets_values": []},
                    {"id": 2, "type": "MiniMaxH3TurboSampler", "inputs": [], "outputs": [], "widgets_values": []},
                    {"id": 3, "type": "MiniMaxH3ImageToVideo", "pos": [0,0], "inputs": [
                        {"name":"clip","link":None}, {"name":"vae","link":None}, {"name":"first_frame","link":None}, {"name":"last_frame","link":None}
                    ], "outputs": [], "widgets_values": []},
                ],
                "links": [], "extra": {},
            }
            (examples / "minimax_h3_t2v_turbo.json").write_text(json.dumps(baseline), encoding="utf-8")
            with patch.dict(os.environ, {"COMFYUI_MINIMAX_H3_TURBO_PATH": str(root)}, clear=False):
                result = create_minimax_h3_turbo_workflow("Use Turbo", mode="flf")
            self.assertTrue(result["ok"])
            self.assertIn("minimax_h3_t2v_turbo.json", result["source_workflow"])
            self.assertEqual(result["workflow"]["extra"]["comfyui_pi_agent"]["integration"], "minimax-h3-turbo")
            self.assertEqual(sum(n["type"] == "LoadImage" for n in result["workflow"]["nodes"]), 2)
            warnings = result["plan"]["warnings"]
            self.assertTrue(any("first-frame placeholder" in item for item in warnings))
            self.assertTrue(any("last-frame placeholder" in item for item in warnings))

    def test_workflow_analyzer_attaches_turbo_report(self):
        workflow = {"nodes": [
            {"id": 1, "type": "MiniMaxH3TurboLoRA", "widgets_values": []},
            {"id": 2, "type": "MiniMaxH3TurboSampler", "widgets_values": []},
        ], "links": []}
        registry = {"MiniMaxH3TurboLoRA": object(), "MiniMaxH3TurboSampler": object()}
        report = analyze_workflow(workflow, live_registry=registry).to_dict()
        self.assertIn("minimax-h3-turbo", report["integrations"])


class PiRuntimeContextIsolationTests(unittest.TestCase):
    def test_rpc_command_disables_eager_pi_context_discovery(self):
        from comfy_pi_agent.pi_runtime import build_pi_command
        command = build_pi_command("pi", provider="test-provider", model="test-model")
        for flag in (
            "--no-approve",
            "--no-context-files",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
            "--no-session",
        ):
            self.assertIn(flag, command)
        self.assertEqual(command[:3], ["pi", "--mode", "rpc"])
        self.assertIn("--provider", command)
        self.assertIn("--model", command)

    def test_one_shot_workflow_context_is_compact_and_on_demand(self):
        from comfy_pi_agent import pi_runtime
        workflow = {
            "nodes": [
                {"id": 1, "type": "LTXDirector", "properties": {"large_payload": "X" * 50000}},
            ],
            "links": [],
        }
        with tempfile.TemporaryDirectory() as td, patch.object(
            pi_runtime, "get_comfy_user_directory", return_value=Path(td)
        ):
            parsed, digest, path = pi_runtime._prepare_workflow_request_context(workflow)
            self.assertEqual(parsed["nodes"][0]["type"], "LTXDirector")
            self.assertLessEqual(len(digest), 20000)
            self.assertNotIn("X" * 1000, digest)
            self.assertIsNotNone(path)
            self.assertTrue(path.is_file())
            self.assertIn("LTXDirector", path.read_text(encoding="utf-8"))
            path.unlink()



if __name__ == "__main__":
    unittest.main()
