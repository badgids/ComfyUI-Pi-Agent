from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SettingsScrollTests(unittest.TestCase):
    def test_settings_panel_scrolls_when_sidebar_height_is_constrained(self):
        js = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn(
            ".pi-agent-settings { padding:8px; border-bottom:1px solid "
            "color-mix(in srgb, currentColor 15%, transparent); display:grid; gap:7px; "
            "flex:0 1 auto; min-height:0; overflow-y:auto; overflow-x:hidden; "
            "overscroll-behavior:contain; scrollbar-gutter:stable; }",
            js,
        )
        self.assertIn(".pi-agent-settings[hidden] { display:none; }", js)


if __name__ == "__main__":
    unittest.main()
