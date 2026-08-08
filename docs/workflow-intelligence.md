# Workflow intelligence

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar chat](sidebar-chat.md) · [Next: Model discovery, safetensors, and GGUF](model-formats-gguf.md)
<!-- DOC_NAV_END -->


## Supported graph formats

- ComfyUI UI workflow: contains a `nodes` list and `links` list.
- ComfyUI API prompt graph: node IDs are object keys and each node has `class_type` and `inputs`.

## Analysis

The analyzer extracts node types, graph order, file-like widget values, model-like filenames, and structural issues. When running inside ComfyUI, it compares types with the live node registry.

## Validation

Legacy `validate_workflow()` remains useful for imported graphs, but generated-workflow completion uses the stricter gate. It compares node classes with the current live ComfyUI registry, validates serialized and live socket/link structure, requires a live output node, and rejects cycles or unverifiable connections.

When an API prompt graph is available, the ComfyUI-Pi HTTP finalizer also calls ComfyUI's own `execution.validate_prompt`. This catches current-instance required-input, combo/model value, node, output, and execution-graph errors before anything is called completion-verified. It does not render media; actual rendering remains separate evidence when requested.

## Generated workflow contract

Generated UI workflows use ComfyUI Nodes 2.0 metadata: `extra.workflowRendererVersion = "Vue-corrected"`. The finalizer lays the graph out deterministically from left to right and enforces at least **6 pixels of empty space between every pair of node rectangles**. Six pixels is the hard minimum; the default organizer intentionally uses larger spacing for readability.

The current live node registry and `/object_info` schemas are authoritative. ComfyUI-Pi must not fabricate a node class or silently substitute an unavailable node. Every link must reference real nodes and slots with compatible datatypes, and node-side link back-references must agree with the top-level link table.

A generated workflow is not complete when it has missing live nodes, bad socket indexes/types, broken link back-references, cycles, insufficient node clearance, no live `OUTPUT_NODE`, or failed native prompt validation.

## Repair

The first release repairs safe container-level problems such as missing API `inputs` objects and invalid top-level arrays. It does not silently replace missing custom nodes.

## Originals

Tutorial compilation writes originals and annotated copies separately. Repair reports should be saved with the original workflow and a diff.

## First-class integration recognition

Workflow analysis can attach integration-specific reports when recognized node packs are present. In v0.1.9, MiniMax H3 Director, WhatDreamsCost-ComfyUI, Scene Camera Action, and MiniMax H3 Turbo are recognized by their public node IDs. The analyzer lazy-loads only the inspector for integrations actually present in the graph.

MiniMax Director analysis checks loader roles, FL2VA/ref2VA models, video/audio VAEs, serialized timeline reference counts, and safe-edit warnings. WhatDreamsCost analysis recognizes its Director and utility nodes and treats frontend-managed timeline state conservatively. Scene Camera Action analysis checks the Scene → Acting → Directing chain plus SceneState safety. H3 Turbo analysis checks the Turbo LoRA/sampler path, scheduler starting profile, MiniMax model/CLIP signals, and joint AV requirements.

Integration context is available to Pi Agent Prompt and the sidebar chat only when the current request/workflow matches. It is not injected at startup. Pi Agent Prompt accepts an optional workflow input; like sidebar chat, it sends a bounded structural digest first and makes the full graph available to Pi on demand rather than pasting a large workflow into the model context.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar chat](sidebar-chat.md) · [Next: Model discovery, safetensors, and GGUF](model-formats-gguf.md)
<!-- DOC_NAV_FOOTER_END -->
