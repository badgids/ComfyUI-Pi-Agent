# ComfyUI-native tutorial compiler

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Complete and incremental production compiler](production-compiler.md) · [Next: Kdenlive and NLE handoff](kdenlive-nle.md)
<!-- DOC_NAV_END -->


## No private WebUI

Tutorials run inside ComfyUI. The compiler does not create or launch a separate web application.

## Inputs

Provide one workflow object, one workflow path, or a JSON list. A list entry can also be an object containing `name`, `source`, and `workflow`.

## Outputs

- preserved original workflow;
- annotated workflow with Pi Tutorial Note nodes;
- stage JSON and stage README;
- Markdown and DOCX complete tutorial;
- requirements and troubleshooting guides;
- model and node manifests;
- Tutorial Controller workflow;
- Project Overview workflow.

## Controller workflow

Load `02_CONTROLLER/Tutorial_Controller.json` in ComfyUI. It contains nodes for loading the tutorial, preflight, stage selection, stage validation, and text display.

## Preflight

Preflight compares required node classes and exact model-like filenames with the running ComfyUI instance. A missing item blocks only the affected tutorial work.

## Documentation screenshots and diagrams

When a tutorial needs **real ComfyUI screenshots**, use the `comfyui_workflow_screenshot` Pi tool rather than recreating the UI. The screenshot broker copies the active serialized workflow into a separate Playwright browser page connected to the same running ComfyUI instance, waits for real Vue nodes/canvas/connections to render, and takes `page.screenshot(clip=...)` PNG captures.

- `mode=workflow` captures the real rendered workflow region.
- `mode=node` locates the target Vue node by `data-node-id`, measures its real DOM bounding box, and keeps **at least 300 CSS pixels of surrounding captured area on every side**.
- The visible user's graph is not temporarily replaced just to capture documentation.
- The optional screenshot backend is installed with `python -m pip install -e '.[screenshots]'`; if necessary, install its Chromium binary with `python -m playwright install chromium`.

For **schematic documentation** rather than a literal screenshot, `comfyui_markdown_node_image` queries the live `/object_info/<node_type>` schema and renders current Nodes 2.0 structure. `comfyui_markdown_flowchart` creates deterministic semantic ASCII plus an independent polished SVG. Existing hand-authored ASCII conversion uses optional Ascidia from `python -m pip install -e '.[diagrams]'`.

See [Installation](installation.md) for optional dependency commands.

## Updating

Compile again into a new version or use future incremental update tools. Originals are stored separately so source workflows are not destroyed.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Complete and incremental production compiler](production-compiler.md) · [Next: Kdenlive and NLE handoff](kdenlive-nle.md)
<!-- DOC_NAV_FOOTER_END -->
