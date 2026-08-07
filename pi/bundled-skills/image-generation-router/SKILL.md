# image-generation-router

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: gguf-model-resolution](../gguf-model-resolution/SKILL.md) · [Next skill: incremental-production-compiler](../incremental-production-compiler/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Select an installed image model and workflow profile for a visual request.

## Procedure

1. Identify text-to-image, image-edit, inpaint, outpaint, or reference mode.
2. Honor an explicit model choice.
3. Rank only installed compatible capabilities.
4. Return missing requirements instead of invented nodes or models.

## Required behavior

- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: gguf-model-resolution](../gguf-model-resolution/SKILL.md) · [Next skill: incremental-production-compiler](../incremental-production-compiler/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
