# workflow-intelligence

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: whatdreamscost-comfyui](../whatdreamscost-comfyui/SKILL.md) · [Next skill: z-image](../z-image/SKILL.md)
<!-- DOC_NAV_END -->


## Purpose

Analyze, validate, repair, explain, and safely modify ComfyUI workflows.

## Procedure

1. Read the exact workflow graph and preserve the original.
2. Query the current ComfyUI instance for the live node catalog. A node type is allowed only when it is registered now (frontend-only Reroute/Note are the only UI exceptions).
3. Query the current live schema for every node that will be created, replaced, or connected. Never infer socket indexes or datatypes from memory.
4. Build and connect the graph from those exact schemas. Every top-level link, node input back-reference, node output back-reference, slot index, and datatype must agree.
5. For UI workflows use Nodes 2.0: set `extra.workflowRendererVersion` to `Vue-corrected`.
6. Organize nodes deterministically from inputs/loaders on the left through processing to output nodes on the right. Keep **at least 6 pixels of empty space between every pair of node rectangles**; never overlap nodes.
7. Require at least one real live `OUTPUT_NODE` and a connected execution path capable of producing the requested media/output.
8. Run `comfyui_workflow_finalize` when that Pi tool is available. Otherwise use `/pi-agent/workflow/finalize`. Fix every reported error and rerun it.
9. When an API prompt graph is available, require ComfyUI's native `execution.validate_prompt` preflight to pass. Static graph validation alone is not completion proof.
10. Only after the gate passes save/return the generated workflow. Return validation evidence and unresolved blockers.

## Required behavior

- Never fabricate, assume, or retain a node class that is absent from the current live ComfyUI registry.
- Never guess connection slots. Use the current instance's live `/object_info` schema.
- Use Nodes 2.0 (`Vue-corrected`) for generated UI workflows.
- Maintain a minimum 6px node-to-node clearance on every generated or reorganized graph.
- A workflow with missing nodes, invalid links, wrong types, no output node, overlapping/too-close nodes, or failed native prompt validation is **not complete and not runnable**.
- Use plain, explicit language.
- Do not hardcode personal paths.
- Do not download models or dependencies during plugin import.
- Preserve originals before edits or repairs.
- Clearly separate static validation, native ComfyUI prompt validation, and actual rendered-output evidence.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: whatdreamscost-comfyui](../whatdreamscost-comfyui/SKILL.md) · [Next skill: z-image](../z-image/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
