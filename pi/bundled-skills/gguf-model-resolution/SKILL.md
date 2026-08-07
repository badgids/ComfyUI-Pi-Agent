# gguf-model-resolution

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: fountain-screenplay](../fountain-screenplay/SKILL.md) · [Next skill: image-generation-router](../image-generation-router/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Resolve validated GGUF alternatives when exact safetensors components are unavailable.

## Procedure

1. Match family, architecture, variant, component role, conditioning, and latent format.
2. Rewrite loader subgraphs instead of changing only filenames.
3. Reject incomplete companion sets.
4. Never infer compatibility from filename alone.

## Required behavior

- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: fountain-screenplay](../fountain-screenplay/SKILL.md) · [Next skill: image-generation-router](../image-generation-router/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
