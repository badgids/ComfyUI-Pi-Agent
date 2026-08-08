# document-export

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: complete-production](../complete-production/SKILL.md) · [Next skill: flux-2-klein-image](../flux-2-klein-image/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Export project text safely as Markdown, DOCX, Fountain, JSON, and deterministic documentation diagrams.

## Procedure

1. Render from structured source objects and preserve the original Markdown before editing it.
2. For every flowchart that ComfyUI-Pi CREATES, call `comfyui_markdown_flowchart` with semantic `nodes` and `edges`. Do not hand-compose ASCII spacing in the prompt and do not use `ascii_text` for newly generated diagrams.
3. The semantic graph is authoritative. Render two independent sibling outputs from it: canonical ASCII using deterministic hierarchical/layered ordering, distinct ports, and orthogonal routing; and a polished vector flowchart using real process/terminal/decision shapes, routed arrows, and edge labels.
4. Keep generated ASCII grammar stable and monospaced: boxes use `+`, `-`, `|`; connectors use `-`, `|`, `+`; arrowheads use `>`, `<`, `^`, `v`; never use tabs. Cycles and back-edges must route outside peer nodes rather than through them.
5. `ascii_text` is reserved for EXISTING hand-authored ASCII supplied by the user or already present in a document. Convert that input with Ascidia's pattern parser when the optional `diagrams` extra is installed. Never trace character cells or create a screenshot-like SVG fallback.
6. Unless the user requests image-only output, keep the readable fenced ASCII diagram and place the independently rendered project-relative SVG immediately with it.
7. For exact tutorial/documentation screenshots of the live ComfyUI UI, use `comfyui_workflow_screenshot`, not a synthetic renderer. `mode=workflow` captures the full currently loaded workflow. `mode=node` captures the actual current Nodes 2.0 Vue node plus surrounding workflow context.
8. Every `mode=node` screenshot MUST leave at least **300 pixels of additional captured area on every side of the target node**. Never request or report a smaller node padding. The screenshot tool may temporarily pan/zoom the live graph to satisfy this and then restores the user's previous view.
9. When a screenshot belongs in Markdown, pass `markdown_path`; the tool writes the PNG beneath the project/cwd safety boundary and inserts a project-relative Markdown image link while preserving a backup.
10. For schematic ComfyUI node illustrations rather than live screenshots, use `comfyui_markdown_node_image`. Resolve the real node from the supplied workflow when possible and query the current ComfyUI `/object_info/<node_type>` schema. Never substitute a generic or legacy LiteGraph drawing.
11. Nodes 2.0 schematic documentation images must use the current v2 structure: rounded node body, separate header/body surfaces, left input slots, right output slots, widgets, live socket names/types, and current v2 design tokens.
12. Use atomic writes, backups, version-safe asset names, and project-relative Markdown image links.
13. PHART is the design reference for hierarchical/layered ordering, spacing, ports, and orthogonal routing. Current PHART releases require Python 3.14, so ComfyUI-Pi implements the compatible routing model internally instead of making PHART a required dependency. Ascidia is the optional parser/renderer for existing ASCII.

## Required behavior

- Generated flowcharts MUST provide semantic nodes and edges; the model is not allowed to invent final ASCII whitespace itself.
- The generated image MUST be a semantic vector rendering of the graph, never an image or tracing of the ASCII output.
- Existing ASCII-only conversion must use Ascidia or fail clearly; never silently fall back to glyph tracing.
- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not invent diagram relationships or ComfyUI node sockets.
- Do not claim a node image is live-schema-correct unless `/object_info` succeeded.
- A live workflow/node screenshot must come from the active ComfyUI browser capture pipeline. Do not replace a failed screenshot with generated artwork or a schematic node renderer.
- Node screenshots must enforce and report at least 300px of padding on the top, right, bottom, and left.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.
- Report the Markdown file and generated diagram/node-image asset paths.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: complete-production](../complete-production/SKILL.md) · [Next skill: flux-2-klein-image](../flux-2-klein-image/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
