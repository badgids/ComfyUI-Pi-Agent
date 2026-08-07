# workflow-intelligence

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: whatdreamscost-comfyui](../whatdreamscost-comfyui/SKILL.md) · [Next skill: z-image](../z-image/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Analyze, validate, repair, explain, and safely modify ComfyUI workflows.

## Procedure

1. Read the exact workflow graph.
2. Inspect live node schemas before suggesting changes.
3. Preserve the original workflow.
4. Return a structured diff and unresolved issues.

## Required behavior

- Use plain, explicit language.
- Inspect live ComfyUI capabilities whenever possible.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate validated behavior from experimental behavior.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: whatdreamscost-comfyui](../whatdreamscost-comfyui/SKILL.md) · [Next skill: z-image](../z-image/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
