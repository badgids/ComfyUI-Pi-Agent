# document-export

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: complete-production](../complete-production/SKILL.md) · [Next skill: flux-2-klein-image](../flux-2-klein-image/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Export project text safely as Markdown, DOCX, Fountain, JSON, and deterministic documentation diagrams.

## Procedure

1. Render from structured source objects and preserve the original Markdown before editing it.
2. For flowcharts, use `comfyui_markdown_flowchart`. Prefer deterministic hierarchical/layered layout with orthogonal connectors.
3. Keep ASCII flowchart grammar stable and monospaced: boxes use `+`, `-`, `|`; connectors use `-`, `|`, `+`; arrowheads use `>`, `<`, `^`, `v`; never use tabs.
4. Unless the user requests image-only output, keep the readable fenced ASCII diagram and place the generated project-relative SVG with it. Existing ASCII can be passed as `ascii_text` and vectorized directly.
5. For ComfyUI node images, use `comfyui_markdown_node_image`. Resolve the real node from the supplied workflow when possible and query the current ComfyUI `/object_info/<node_type>` schema. Never substitute a generic or legacy LiteGraph drawing.
6. Nodes 2.0 documentation images must use the current v2 structure: rounded node body, separate header/body surfaces, left input slots, right output slots, widgets, live socket names/types, and current v2 design tokens.
7. Use atomic writes, backups, version-safe asset names, and project-relative Markdown image links.
8. PHART and Ascidia are design references for deterministic graph layout/routing and ASCII vectorization; they are not mandatory runtime dependencies.

## Required behavior

- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not invent diagram relationships or ComfyUI node sockets.
- Do not claim a node image is live-schema-correct unless `/object_info` succeeded.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.
- Report the Markdown file and generated diagram/node-image asset paths.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: complete-production](../complete-production/SKILL.md) · [Next skill: flux-2-klein-image](../flux-2-klein-image/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
