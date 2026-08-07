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

## Updating

Compile again into a new version or use future incremental update tools. Originals are stored separately so source workflows are not destroyed.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Complete and incremental production compiler](production-compiler.md) · [Next: Kdenlive and NLE handoff](kdenlive-nle.md)
<!-- DOC_NAV_FOOTER_END -->
