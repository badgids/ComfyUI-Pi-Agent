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
        self.assertEqual(namespace["__version__"], "0.1.16")


if __name__ == "__main__":
    unittest.main()
