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
7. For tutorial/documentation screenshots of the live ComfyUI UI, use `comfyui_workflow_screenshot`. The visible browser supplies the serialized workflow, then a separate Playwright page loads it into the same running ComfyUI frontend and captures the actual rendered page with `page.screenshot(clip=...)`.
8. `comfyui_workflow_screenshot` with `mode=node` is a **context screenshot**: it MUST use the real Vue node DOM bounding box (`.lg-node` / `data-node-id`) and leave at least **300 CSS pixels of surrounding captured area on every side**. Never request or report a smaller context margin for that tool.
9. `mode=workflow` must capture the actual Playwright-rendered workflow region, including the real ComfyUI canvas, connections, Vue node styling, widgets, sockets, and current frontend theme. Do not rebuild nodes with HTML/CSS, SVG `foreignObject`, canvas-layer compositing, or generated artwork.
10. For a standalone exact image of an installed ComfyUI node, use `comfyui_markdown_node_image`. Resolve the real workflow node when supplied and validate its node type through the current `/object_info/<node_type>` endpoint when the type is known.
11. `comfyui_markdown_node_image` MUST let the current ComfyUI frontend instantiate and render the node, then crop the PNG to the measured real Vue node DOM bounds with **zero artificial context padding**. The running ComfyUI frontend is the sole visual authority.
12. When only `node_type` is supplied, ComfyUI-Pi may load a minimal one-node serialized workflow containing only identity/position/container fields needed for ComfyUI to instantiate the registered node. It MUST NOT invent sockets, widget controls, colors, labels, values, or custom frontend content; ComfyUI and the installed node pack create those.
13. If the installed node cannot be rendered or its real DOM bounds cannot be measured, fail clearly. Never fall back to a generated SVG, HTML/CSS recreation, Canvas drawing, generic LiteGraph node, or any other approximation.
14. When an image belongs in Markdown, the tool writes the PNG beneath the project/cwd safety boundary, preserves a backup, and inserts a project-relative Markdown image link.
15. The Playwright backend is an optional runtime extra: `python -m pip install -e '.[screenshots]'`. If no system Chromium/Chrome is available, install Playwright Chromium with `python -m playwright install chromium`.
16. Use atomic writes, backups, version-safe asset names, and project-relative Markdown image links.
17. PHART is the design reference for hierarchical/layered flowchart ordering, spacing, ports, and orthogonal routing. Current PHART releases require Python 3.14, so ComfyUI-Pi implements the compatible routing model internally instead of making PHART a required dependency. Ascidia is the optional parser/renderer for existing ASCII.

## Required behavior

- Generated flowcharts MUST provide semantic nodes and edges; the model is not allowed to invent final ASCII whitespace itself.
- The generated flowchart image MUST be a semantic vector rendering of the graph, never an image or tracing of the ASCII output.
- Existing ASCII-only conversion must use Ascidia or fail clearly; never silently fall back to glyph tracing.
- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not invent diagram relationships or ComfyUI node sockets.
- Do not claim an installed node type was validated unless `/object_info` succeeded.
- A live workflow or node image must come from Playwright's real browser `page.screenshot(clip=...)` path after the real ComfyUI frontend loads the serialized workflow/node. Never replace a failed capture with generated artwork or reconstruction.
- `comfyui_workflow_screenshot mode=node` must enforce and report at least 300px of context on every side of the measured Vue node bounding box.
- `comfyui_markdown_node_image` must enforce the opposite contract: exact measured node bounds, zero artificial context padding, and output dimensions equal to the measured rendered node dimensions at the selected device scale.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.
- Report the Markdown file and generated diagram/node-image asset paths.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: complete-production](../complete-production/SKILL.md) · [Next skill: flux-2-klein-image](../flux-2-klein-image/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
