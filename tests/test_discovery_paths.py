import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.compat import (
    get_comfy_search_path_registry,
    get_comfy_search_paths,
    get_comfy_workflow_roots,
)
from comfy_pi_agent.discovery import find_installed_assets, installation_search_context, search_path_inventory
from comfy_pi_agent.models import inventory_models

ROOT = Path(__file__).resolve().parents[1]


class ComfySearchPathTests(unittest.TestCase):
    def fake_folder_paths(self, root: Path):
        default_models = root / "ComfyUI" / "models" / "checkpoints"
        extra_models = root / "SharedModels" / "checkpoints"
        default_nodes = root / "ComfyUI" / "custom_nodes"
        extra_nodes = root / "SharedNodes"
        extra_workflows = root / "SharedWorkflows"
        extra_assets = root / "SharedAssets"
        user_root = root / "ComfyUI" / "user"
        for path in (default_models, extra_models, default_nodes, extra_nodes, extra_workflows, extra_assets, user_root / "default" / "workflows"):
            path.mkdir(parents=True, exist_ok=True)

        (extra_models / "extra-model.safetensors").write_text("model", encoding="utf-8")
        pack = extra_nodes / "External-Pack"
        (pack / "example_workflows").mkdir(parents=True)
        (pack / "__init__.py").write_text("", encoding="utf-8")
        (pack / "example_workflows" / "pack-workflow.json").write_text("{}", encoding="utf-8")
        (extra_workflows / "external-workflow.json").write_text("{}", encoding="utf-8")
        (extra_assets / "reference.dat").write_text("asset", encoding="utf-8")

        module = types.ModuleType("folder_paths")
        module.folder_names_and_paths = {
            "checkpoints": ([str(default_models), str(extra_models)], {".safetensors"}),
            "custom_nodes": ([str(default_nodes), str(extra_nodes)], set()),
            "workflows": ([str(extra_workflows)], {".json"}),
            "reference_assets": ([str(extra_assets)], {".dat"}),
        }
        module.get_folder_paths = lambda category: list(module.folder_names_and_paths[category][0])
        def get_filename_list(category):
            if category == "checkpoints":
                return ["extra-model.safetensors"]
            if category == "workflows":
                return ["external-workflow.json"]
            if category == "reference_assets":
                return ["reference.dat"]
            return []
        module.get_filename_list = get_filename_list
        module.get_user_directory = lambda: str(user_root)
        return module, {
            "default_models": default_models,
            "extra_models": extra_models,
            "default_nodes": default_nodes,
            "extra_nodes": extra_nodes,
            "extra_workflows": extra_workflows,
            "extra_assets": extra_assets,
        }

    def test_live_registry_includes_default_and_extra_paths(self):
        with tempfile.TemporaryDirectory() as td:
            fake, paths = self.fake_folder_paths(Path(td))
            with patch.dict(sys.modules, {"folder_paths": fake}):
                model_roots = get_comfy_search_paths("checkpoints")
                node_roots = get_comfy_search_paths("custom_nodes")
                registry = get_comfy_search_path_registry()
            self.assertEqual(model_roots, [paths["default_models"].resolve(), paths["extra_models"].resolve()])
            self.assertEqual(node_roots, [paths["default_nodes"].resolve(), paths["extra_nodes"].resolve()])
            self.assertIn(paths["extra_models"].resolve(), registry["checkpoints"])
            self.assertIn(paths["extra_nodes"].resolve(), registry["custom_nodes"])

    def test_runtime_guidance_exposes_extra_roots_only_when_discovery_is_relevant(self):
        with tempfile.TemporaryDirectory() as td:
            fake, paths = self.fake_folder_paths(Path(td))
            with patch.dict(sys.modules, {"folder_paths": fake}):
                context = installation_search_context("Find my installed workflow and custom node pack")
                unrelated = installation_search_context("Write a short story")
            self.assertIn(str(paths["extra_nodes"].resolve()), context)
            self.assertIn(str(paths["extra_workflows"].resolve()), context)
            self.assertEqual(unrelated, "")

    def test_model_inventory_reports_live_search_roots(self):
        with tempfile.TemporaryDirectory() as td:
            fake, paths = self.fake_folder_paths(Path(td))
            with patch.dict(sys.modules, {"folder_paths": fake}):
                inventory = inventory_models(limit_per_category=10)
            self.assertEqual(inventory["search_path_source"], "live_comfyui_folder_paths")
            self.assertIn(str(paths["extra_models"].resolve()), inventory["search_paths"]["checkpoints"])
            self.assertEqual(inventory["categories"]["checkpoints"][0]["name"], "extra-model.safetensors")

    def test_agent_exposes_live_path_and_asset_discovery_tools(self):
        bridge = (ROOT / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        routes = (ROOT / "comfy_pi_agent" / "routes.py").read_text(encoding="utf-8")
        guidance = (ROOT / "comfy_pi_agent" / "agent_guidance.py").read_text(encoding="utf-8")
        self.assertIn('name: "comfyui_search_paths"', bridge)
        self.assertIn('name: "comfyui_find_installed"', bridge)
        self.assertIn('/pi-agent/discovery/paths', routes)
        self.assertIn('/pi-agent/discovery/find', routes)
        self.assertIn('extra_model_paths.yaml', guidance)
        self.assertIn('--extra-model-paths-config', guidance)


    def test_explicit_registered_category_uses_live_extra_path(self):
        with tempfile.TemporaryDirectory() as td:
            fake, paths = self.fake_folder_paths(Path(td))
            with patch.dict(sys.modules, {"folder_paths": fake}):
                result = find_installed_assets("reference", categories=["reference_assets"])
            self.assertEqual(result["kinds"], ["registered"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["matches"][0]["category"], "reference_assets")
            self.assertIn(str(paths["extra_assets"].resolve() / "reference.dat"), result["matches"][0]["paths"])

    def test_workflow_roots_include_registered_extra_paths(self):
        with tempfile.TemporaryDirectory() as td:
            fake, paths = self.fake_folder_paths(Path(td))
            with patch.dict(sys.modules, {"folder_paths": fake}):
                roots = get_comfy_workflow_roots()
            self.assertIn(paths["extra_workflows"].resolve(), roots)

    def test_asset_finder_searches_extra_models_workflows_and_custom_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            fake, paths = self.fake_folder_paths(Path(td))
            with patch.dict(sys.modules, {"folder_paths": fake}):
                models = find_installed_assets("extra-model", kinds=["models"])
                workflows = find_installed_assets("external-workflow", kinds=["workflows"])
                pack_workflow = find_installed_assets("pack-workflow", kinds=["workflows"])
                nodes = find_installed_assets("External-Pack", kinds=["custom_nodes"])
                inventory = search_path_inventory()

            self.assertEqual(models["count"], 1)
            self.assertIn(str(paths["extra_models"].resolve() / "extra-model.safetensors"), models["matches"][0]["paths"])
            self.assertEqual(workflows["count"], 1)
            self.assertEqual(Path(workflows["matches"][0]["path"]).resolve(), paths["extra_workflows"].resolve() / "external-workflow.json")
            self.assertEqual(pack_workflow["count"], 1)
            self.assertEqual(nodes["count"], 1)
            self.assertEqual(Path(nodes["matches"][0]["root"]).resolve(), paths["extra_nodes"].resolve())
            category_paths = {row["path"] for row in inventory["categories"]["custom_nodes"]}
            self.assertIn(str(paths["extra_nodes"].resolve()), category_paths)


if __name__ == "__main__":
    unittest.main()
