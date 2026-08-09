import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LicenseAndReleaseTests(unittest.TestCase):
    def test_project_is_gpl3(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", license_text[:200])
        self.assertIn("Version 3", license_text[:200])
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('license = { text = "GPL-3.0-only" }', pyproject)

    def test_bundled_skill_metadata_is_gpl3(self):
        for path in (ROOT / "pi" / "bundled-skills").glob("*/skill.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("license"), "GPL-3.0", path.name)

    def test_release_version(self):
        namespace = {}
        exec((ROOT / "comfy_pi_agent" / "version.py").read_text(encoding="utf-8"), namespace)
        self.assertEqual(namespace["__version__"], "0.1.18")
        self.assertIn('version = "0.1.18"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn("**Release:** 0.1.18", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("- Version: 0.1.18", (ROOT / "PROJECT_INVENTORY.md").read_text(encoding="utf-8"))
        self.assertIn("## 0.1.18", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertIn("# Release notes — 0.1.18", (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8"))

    def test_optional_feature_installation_is_documented(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "installation.md").read_text(encoding="utf-8")
        self.assertIn('diagrams = [', pyproject)
        self.assertIn('"ascidia>=2.0.1,<3"', pyproject)
        self.assertIn('screenshots = [', pyproject)
        self.assertIn('"playwright>=1.50,<2"', pyproject)
        self.assertIn("python -m pip install -e '.[diagrams]'", install)
        self.assertIn("python -m pip install -e '.[screenshots]'", install)
        self.assertIn("python -m pip install -e '.[diagrams,screenshots]'", install)
        self.assertIn("python -m playwright install chromium", install)

    def test_current_docs_describe_same_session_compaction(self):
        current_docs = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "docs/architecture.md",
                "docs/context-handoff.md",
                "docs/dynamic-integration-context.md",
                "docs/pi-terminal.md",
                "docs/pi-runtime.md",
                "docs/sidebar-chat.md",
                "docs/small-model-reliability.md",
            )
        )
        self.assertIn("same-session", current_docs)
        self.assertIn("turn_end", current_docs)
        self.assertNotIn("starts a fresh Pi session with native `/new`", current_docs)
        self.assertNotIn("waiting for the safe same-session compaction boundary", current_docs)

    def test_release_manifest_has_regenerator(self):
        tool = (ROOT / "tools" / "regenerate_manifest.py").read_text(encoding="utf-8")
        development = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
        self.assertIn('EXCLUDED_PATHS = {"MANIFEST.json"}', tool)
        self.assertIn('"--cached"', tool)
        self.assertIn('"--others"', tool)
        self.assertIn('"--exclude-standard"', tool)
        self.assertIn('"--check"', tool)
        self.assertIn("python tools/regenerate_manifest.py --check", development)



if __name__ == "__main__":
    unittest.main()
