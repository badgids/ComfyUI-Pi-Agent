import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from comfy_pi_agent.docx_writer import write_docx
from comfy_pi_agent.projects import PROJECT_DIRECTORY_LAYOUT, compile_project, create_project_plan


class DocumentProjectTests(unittest.TestCase):
    def test_docx(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.docx"
            write_docx(path, "# Title\n\nHello", "Title")
            self.assertTrue(path.is_file())
            with zipfile.ZipFile(path) as archive:
                self.assertIn("word/document.xml", archive.namelist())

    def test_project_plan(self):
        plan = create_project_plan("Create a short film with dialogue.", "Test Film")
        self.assertEqual(plan["project_id"], "Test-Film")
        self.assertTrue(plan["capability_flags"]["narrative"])
        self.assertTrue(plan["capability_flags"]["audio"])
        self.assertIn("01_STORY", plan["project_directories"])
        self.assertIn("04_MOOD_BOARDS", plan["project_directories"])
        self.assertIn("06_STORYBOARDS", plan["project_directories"])

    def test_compile_project_creates_explicit_asset_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            result = compile_project("Create a short film.", "Test Film", temp)
            root = Path(result["project_root"])

            self.assertTrue((root / "START_HERE.md").is_file())
            self.assertTrue((root / "PROJECT_DIRECTORY_GUIDE.md").is_file())
            self.assertTrue((root / "PROJECT_DIRECTORY_GUIDE.docx").is_file())
            self.assertTrue((root / "00_PROJECT_ADMIN" / "PROJECT_BRIEF.md").is_file())
            self.assertTrue((root / "01_STORY" / "04_MANUSCRIPT" / "story.md").is_file())
            self.assertTrue((root / "02_SCREENPLAY" / "01_FOUNTAIN" / "screenplay.fountain").is_file())
            self.assertTrue((root / "04_MOOD_BOARDS" / "mood-board-manifest.json").is_file())
            self.assertTrue((root / "05_REFERENCE_SHEETS" / "reference-sheet-manifest.json").is_file())
            self.assertTrue((root / "06_STORYBOARDS" / "storyboard-manifest.json").is_file())
            self.assertTrue((root / "07_SCENE_AND_SHOT_PLANS" / "03_SHOT_LISTS" / "shot-list.json").is_file())
            self.assertTrue((root / "08_PROMPTS" / "prompt-manifest.json").is_file())
            self.assertTrue((root / "09_COMFYUI_WORKFLOWS" / "workflow-manifest.json").is_file())
            self.assertTrue((root / "12_NLE_PROJECT" / "05_ASSEMBLY_GUIDES" / "ASSEMBLE_IN_KDENLIVE.md").is_file())

            manifest_path = root / "00_PROJECT_ADMIN" / "01_MANIFESTS" / "production-manifest.json"
            asset_catalog_path = root / "00_PROJECT_ADMIN" / "01_MANIFESTS" / "asset-catalog.json"
            directory_map_path = root / "00_PROJECT_ADMIN" / "01_MANIFESTS" / "directory-map.json"
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(asset_catalog_path.is_file())
            self.assertTrue(directory_map_path.is_file())

            manifest = json.loads(manifest_path.read_text())
            catalog = json.loads(asset_catalog_path.read_text())
            self.assertEqual(manifest["status"], "planned")
            self.assertEqual(catalog["asset_roots"]["mood_boards"], "04_MOOD_BOARDS")
            self.assertEqual(catalog["asset_roots"]["storyboards"], "06_STORYBOARDS")

    def test_every_labeled_directory_has_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(compile_project("Create a movie project.", "Labeled Project", temp)["project_root"])
            for section in PROJECT_DIRECTORY_LAYOUT:
                top = root / section["path"]
                self.assertTrue((top / "README.md").is_file(), section["path"])
                for subdirectory, _purpose in section["subdirectories"]:
                    child = top / subdirectory
                    self.assertTrue((child / "README.md").is_file(), str(child))


if __name__ == "__main__":
    unittest.main()
