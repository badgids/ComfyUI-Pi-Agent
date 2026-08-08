import json
import tempfile
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
        {"id": "inspect", "label": "Inspect live nodes"},
        {"id": "build", "label": "Build workflow"},
        {"id": "validate", "label": "Validate output"},
    ],
    "edges": [
        {"from": "inspect", "to": "build"},
        {"from": "build", "to": "validate"},
    ],
}


class MarkdownDiagramTests(unittest.TestCase):
    def test_ascii_flowchart_is_deterministic_and_orthogonal(self):
        first = render_flowchart_ascii(FLOW)
        second = render_flowchart_ascii(FLOW)
        self.assertEqual(first, second)
        self.assertIn("+--------------------+", first)
        self.assertIn("Inspect live nodes", first)
        self.assertIn("v", first)
        self.assertNotIn("\t", first)
        self.assertTrue(all(not line.endswith(" ") for line in first.splitlines()))

    def test_existing_ascii_flowchart_vectorizes_lines_and_arrows(self):
        ascii_text = "+-----+\n| One |\n+--+--+\n   |\n   v\n+-----+\n| Two |\n+-----+\n"
        svg = render_ascii_text_svg(ascii_text)
        self.assertIn("<svg", svg)
        self.assertIn("<path", svg)
        self.assertIn("<polygon", svg)
        self.assertIn("One", svg)
        self.assertIn("Two", svg)

    def test_flowchart_svg_is_vector_image(self):
        svg = render_flowchart_svg(FLOW)
        self.assertIn("<svg", svg)
        self.assertIn("<rect", svg)
        self.assertIn("<path", svg)
        self.assertIn('marker-end="url(#arrow)"', svg)
        self.assertIn("Inspect live nodes", svg)

    def test_markdown_flowchart_writes_ascii_and_relative_svg(self):
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
            "id": 3,
            "type": "KSampler",
            "size": [315, 260],
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
                    "id": 7,
                    "type": "KSampler",
                    "title": "Sampler",
                    "size": [315, 240],
                    "inputs": [{"name": "model", "type": "MODEL", "link": None}],
                    "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                    "widgets_values": [42],
                }],
                "links": [],
            }), encoding="utf-8")
            live = {
                "display_name": "KSampler",
                "input": {"required": {"model": ["MODEL", {}], "seed": ["INT", {"default": 0}]}},
                "output": ["LATENT"],
                "output_name": ["LATENT"],
            }
            with patch("comfy_pi_agent.markdown_diagrams._fetch_live_object_info", return_value=live) as fetch:
                result = create_comfyui_v2_node_markdown(
                    str(markdown),
                    "http://127.0.0.1:8188",
                    workflow_path=str(workflow),
                    node_id="7",
                )
            fetch.assert_called_once_with("http://127.0.0.1:8188", "KSampler")
            self.assertTrue(result["live_schema_verified"])
            self.assertTrue(Path(result["image_path"]).is_file())
            text = markdown.read_text(encoding="utf-8")
            self.assertIn("![Sampler](nodes_assets/node-7.svg)", text)


    def test_terminal_bridge_exposes_markdown_diagram_tools(self):
        root = Path(__file__).resolve().parents[1]
        bridge = (root / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn('name: "comfyui_markdown_flowchart"', bridge)
        self.assertIn('name: "comfyui_markdown_node_image"', bridge)
        self.assertIn("comfy_pi_agent.markdown_diagram_cli", bridge)


if __name__ == "__main__":
    unittest.main()
