import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.markdown_diagrams import (
    COMFY_V2_DARK,
    create_comfyui_v2_node_markdown,
    create_flowchart_markdown,
    render_ascii_text_svg,
    render_comfyui_v2_node_svg,
    render_flowchart_ascii,
    render_flowchart_svg,
)

FLOW = {
    "direction": "TB",
    "nodes": [
        {"id": "inspect", "label": "Inspect live nodes", "shape": "start"},
        {"id": "build", "label": "Build workflow"},
        {"id": "validate", "label": "Validate output", "shape": "end"},
    ],
    "edges": [
        {"from": "inspect", "to": "build"},
        {"from": "build", "to": "validate"},
    ],
}

BRANCH = {
    "direction": "TB",
    "nodes": [
        {"id": "start", "label": "Start", "shape": "start"},
        {"id": "decision", "label": "Ready?", "shape": "decision"},
        {"id": "yes", "label": "Run workflow"},
        {"id": "no", "label": "Repair inputs"},
        {"id": "done", "label": "Done", "shape": "end"},
    ],
    "edges": [
        {"from": "start", "to": "decision"},
        {"from": "decision", "to": "yes", "label": "yes"},
        {"from": "decision", "to": "no", "label": "no"},
        {"from": "yes", "to": "done"},
        {"from": "no", "to": "done"},
    ],
}

CYCLE = {
    "direction": "TB",
    "nodes": [
        {"id": "start", "label": "Start", "shape": "start"},
        {"id": "inspect", "label": "Inspect live ComfyUI nodes"},
        {"id": "decision", "label": "All required nodes available?", "shape": "decision"},
        {"id": "build", "label": "Build and connect workflow"},
        {"id": "repair", "label": "Repair missing nodes"},
        {"id": "validate", "label": "Validate with ComfyUI"},
        {"id": "done", "label": "Output verified", "shape": "end"},
    ],
    "edges": [
        {"from": "start", "to": "inspect"},
        {"from": "inspect", "to": "decision"},
        {"from": "decision", "to": "build", "label": "yes"},
        {"from": "decision", "to": "repair", "label": "no"},
        {"from": "repair", "to": "inspect", "label": "retry"},
        {"from": "build", "to": "validate"},
        {"from": "validate", "to": "done"},
    ],
}


class MarkdownDiagramTests(unittest.TestCase):
    def test_ascii_flowchart_is_deterministic_and_orthogonal(self):
        first = render_flowchart_ascii(FLOW)
        second = render_flowchart_ascii(FLOW)
        self.assertEqual(first, second)
        self.assertIn("Inspect live nodes", first)
        self.assertIn("Build workflow", first)
        self.assertIn("Validate output", first)
        self.assertIn("v", first)
        self.assertNotIn("\t", first)
        self.assertTrue(all(not line.endswith(" ") for line in first.splitlines()))

    def test_branch_ascii_has_stable_labels_and_no_collapsed_boxes(self):
        ascii_chart = render_flowchart_ascii(BRANCH)
        self.assertIn("Ready?", ascii_chart)
        self.assertIn("yes", ascii_chart)
        self.assertIn("no", ascii_chart)
        self.assertIn("Run workflow", ascii_chart)
        self.assertIn("Repair inputs", ascii_chart)
        self.assertNotIn("++", ascii_chart)
        self.assertNotIn("\t", ascii_chart)

    def test_cycle_back_edge_routes_outside_without_overwriting_main_node(self):
        ascii_chart = render_flowchart_ascii(CYCLE)
        self.assertIn("retry", ascii_chart)
        self.assertIn("| Build and connect workflow  |", ascii_chart)
        self.assertIn("| Repair missing nodes  |", ascii_chart)
        self.assertNotIn("Build and connect workflow--", ascii_chart)
        self.assertTrue(all(not line.endswith(" ") for line in ascii_chart.splitlines()))

    def test_semantic_svg_is_independent_polished_graphics_not_ascii_trace(self):
        svg = render_flowchart_svg(BRANCH)
        self.assertIn("<svg", svg)
        self.assertIn("<linearGradient", svg)
        self.assertIn('opacity="0.10"', svg)
        self.assertNotIn("feDropShadow", svg)
        self.assertIn("<polygon", svg)  # decision node is a real diamond
        self.assertIn('marker-end="url(#arrow)"', svg)
        self.assertIn("Inter,ui-sans-serif,system-ui", svg)
        self.assertNotIn("ui-monospace", svg)
        self.assertNotIn("SFMono-Regular", svg)

    def test_semantic_spec_ignores_bad_model_ascii_for_both_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "README.md"
            result = create_flowchart_markdown(
                str(markdown), FLOW, diagram_id="semantic", ascii_text="BROKEN ASCII SPACING"
            )
            svg = Path(result["image_path"]).read_text(encoding="utf-8")
            self.assertEqual(result["image_source"], "semantic-graph")
            self.assertEqual(result["ascii_source"], "semantic-graph")
            self.assertNotIn("BROKEN ASCII SPACING", result["ascii"])
            self.assertNotIn("BROKEN ASCII SPACING", svg)
            self.assertIn("Inspect live nodes", result["ascii"])
            self.assertIn("Inspect live nodes", svg)

    def test_existing_ascii_uses_ascidia_pattern_renderer_not_glyph_tracing(self):
        calls = {"processed": None, "diagram": None}

        class FakeSvgOutput:
            @staticmethod
            def output(diagram, stream, prefs):
                calls["diagram"] = diagram
                stream.write('<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="100" height="50"/></svg>')

        fake = types.SimpleNamespace(
            process_diagram=lambda text: calls.__setitem__("processed", text) or {"semantic": "diagram"},
            SvgOutput=FakeSvgOutput,
            OutputPrefs=lambda **kwargs: kwargs,
            NAMED_COLOURS={"black": (0, 0, 0), "white": (1, 1, 1)},
        )
        ascii_text = "+-----+\n| One |\n+--+--+\n   |\n   v\n+-----+\n| Two |\n+-----+\n"
        with patch.dict(sys.modules, {"ascidia": fake}):
            svg = render_ascii_text_svg(ascii_text)
        self.assertEqual(calls["processed"], ascii_text)
        self.assertEqual(calls["diagram"], {"semantic": "diagram"})
        self.assertIn("<rect", svg)
        self.assertNotIn("One", svg)  # proves this test did not use character-by-character text tracing

    def test_existing_ascii_without_ascidia_fails_instead_of_fake_svg(self):
        with patch.dict(sys.modules, {"ascidia": None}):
            with self.assertRaisesRegex(RuntimeError, "Ascidia is not installed"):
                render_ascii_text_svg("+---+\n| A |\n+---+\n")

    def test_markdown_flowchart_writes_canonical_ascii_and_relative_semantic_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            markdown = root / "README.md"
            markdown.write_text("# Demo\n\n<!-- comfyui-pi-insert:diagram:build-flow -->\n", encoding="utf-8")
            result = create_flowchart_markdown(
                str(markdown), FLOW, diagram_id="build-flow", alt_text="Build flow", include_ascii=True
            )
            text = markdown.read_text(encoding="utf-8")
            self.assertTrue(Path(result["image_path"]).is_file())
            self.assertIn("```text", text)
            self.assertIn("![Build flow](README_assets/build-flow.svg)", text)
            self.assertEqual(result["renderer"], "comfyui-pi-semantic-vector-svg")
            self.assertNotIn(str(root), text)
            self.assertTrue(result["backup_path"])

    def test_flowchart_upsert_replaces_owned_block_instead_of_duplicating(self):
        with tempfile.TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "guide.md"
            create_flowchart_markdown(str(markdown), FLOW, diagram_id="same")
            create_flowchart_markdown(str(markdown), FLOW, diagram_id="same")
            text = markdown.read_text(encoding="utf-8")
            self.assertEqual(text.count("<!-- comfyui-pi:diagram:same:start -->"), 1)
            self.assertEqual(text.count("![Flowchart](guide_assets/same.svg)"), 1)

    def test_v2_node_svg_uses_current_comfyui_v2_structure_and_dark_tokens(self):
        info = {
            "display_name": "KSampler",
            "input": {
                "required": {
                    "model": ["MODEL", {}],
                    "seed": ["INT", {"default": 0}],
                    "positive": ["CONDITIONING", {}],
                }
            },
            "output": ["LATENT"],
            "output_name": ["LATENT"],
        }
        node = {
            "id": 3, "type": "KSampler", "size": [315, 260],
            "inputs": [
                {"name": "model", "type": "MODEL", "link": 1},
                {"name": "positive", "type": "CONDITIONING", "link": 2},
            ],
            "outputs": [{"name": "LATENT", "type": "LATENT", "links": [3]}],
            "widgets_values": [12345],
        }
        svg = render_comfyui_v2_node_svg("KSampler", info, node)
        self.assertIn(COMFY_V2_DARK["background"], svg)
        self.assertIn(COMFY_V2_DARK["header"], svg)
        self.assertIn('rx="12"', svg)
        self.assertIn("<circle", svg)
        self.assertIn("positive", svg)
        self.assertIn("LATENT", svg)
        self.assertIn("KSampler", svg)

    def test_node_markdown_requires_live_object_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            markdown = root / "nodes.md"
            workflow = root / "workflow.json"
            workflow.write_text(json.dumps({
                "nodes": [{
                    "id": 7, "type": "KSampler", "title": "Sampler", "size": [315, 240],
                    "inputs": [{"name": "model", "type": "MODEL", "link": None}],
                    "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                    "widgets_values": [42],
                }],
                "links": [],
            }), encoding="utf-8")
            live = {
                "display_name": "KSampler",
                "input": {"required": {"model": ["MODEL", {}], "seed": ["INT", {"default": 0}]}},
                "output": ["LATENT"], "output_name": ["LATENT"],
            }
            with patch("comfy_pi_agent.markdown_diagrams._fetch_live_object_info", return_value=live) as fetch:
                result = create_comfyui_v2_node_markdown(
                    str(markdown), "http://127.0.0.1:8188", workflow_path=str(workflow), node_id="7"
                )
            fetch.assert_called_once_with("http://127.0.0.1:8188", "KSampler")
            self.assertTrue(result["live_schema_verified"])
            self.assertTrue(Path(result["image_path"]).is_file())
            self.assertIn("![Sampler](nodes_assets/node-7.svg)", markdown.read_text(encoding="utf-8"))

    def test_terminal_bridge_exposes_markdown_diagram_tools(self):
        root = Path(__file__).resolve().parents[1]
        bridge = (root / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn('name: "comfyui_markdown_flowchart"', bridge)
        self.assertIn('name: "comfyui_markdown_node_image"', bridge)
        self.assertIn("comfy_pi_agent.markdown_diagram_cli", bridge)
        self.assertIn("semantic", bridge.lower())


if __name__ == "__main__":
    unittest.main()
