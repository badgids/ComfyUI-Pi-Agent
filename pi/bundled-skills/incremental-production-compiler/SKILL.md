# incremental-production-compiler

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: image-generation-router](../image-generation-router/SKILL.md) · [Next skill: kdenlive-handoff](../kdenlive-handoff/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Compile a whole project or only selected stages, scenes, shots, missing, or stale assets.

## Procedure

1. Build a dependency graph.
2. Calculate invalidation before rebuilding.
3. Resume from checkpoints.
4. Isolate failures to affected stages.

## Required behavior

- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: image-generation-router](../image-generation-router/SKILL.md) · [Next skill: kdenlive-handoff](../kdenlive-handoff/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
