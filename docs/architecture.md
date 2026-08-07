# Architecture

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Troubleshooting](troubleshooting.md) · [Next: Compatibility](compatibility.md)
<!-- DOC_NAV_END -->


## Layers

1. ComfyUI nodes in `comfy_pi_agent/nodes.py`.
2. Shared services for workflows, models, Fountain, projects, tutorials, NLE, DOCX, and Pi RPC.
3. Optional routes in `comfy_pi_agent/routes.py`.
4. Optional ComfyUI frontend extension in `web/pi_agent.js`.
5. Interoperability adapters in `comfy_pi_agent/integrations/` for explicitly supported third-party node packs.
6. Host-side weak-model guidance and deterministic task-skill routing in `comfy_pi_agent/agent_guidance.py`.
7. Data profiles and original Pi skills.

## Design rules

- Nodes call services instead of duplicating logic.
- Services can run in tests without ComfyUI.
- ComfyUI imports are isolated in compatibility helpers.
- Optional route failures are logged instead of raising through plugin import.
- File mutations are atomic.

## Third-party integration rule

An integration adapter may describe public node IDs, live schemas, component roles, and validated operating rules. It should not copy third-party implementation code. When a third-party pack owns complex serialized frontend state, ComfyUI-Pi prefers that pack's installed example workflows and UI instead of guessing undocumented widget indexes.

MiniMax H3 Director, WhatDreamsCost-ComfyUI, Scene Camera Action, and MiniMax H3 Turbo all use this pattern in release 0.1.9.

## Weak-model guidance layer

ComfyUI-Pi treats model capability as an unreliable dependency. The host determines the task class and matching bundled procedures before prompting Pi. The model receives one current-job envelope, a small core contract, and at most a few relevant procedure documents. Procedure IDs participate in the scope signature so stale hidden instructions are discarded when the task changes.

See [small-model-reliability.md](small-model-reliability.md).

## Lazy integration knowledge

Third-party node-pack knowledge is not part of the permanent Pi system context.

`data/integrations/registry.json` is the small discovery layer. It contains only public node IDs, matching phrases, module names, and skill-file locations.

The supervised Pi RPC process also disables automatic project context files, extension discovery, skill discovery, prompt-template discovery, theme discovery, and project trust for that run. The integration registry remains host-side.

For each Pi request:

```text
message + optional active workflow
        ↓
host-side small integration registry
        ↓
match node IDs / explicit terms
        ↓
load only matching adapter module
        ↓
build compact task-targeted context
        ↓
full SKILL.md only for explicit comprehensive guide/tutorial/deep-dive
        ↓
apply per-integration and total context budget
        ↓
Pi request
```

An unrelated request skips the adapter import and skill-file read entirely. A normal matched request also skips the full skill-file read.

Workflow analysis uses the same strategy: only inspectors for node packs actually present in the graph are imported.


## Context lifecycle

Stateful sidebar chat uses a host-controlled context lifecycle:

```text
Pi usage + get_state contextWindow
        ↓
82.5% default threshold (configurable 80–95%)
        ↓
fresh-process handoff summarizer
        ↓
bounded Markdown handoff on disk
        ↓
active Pi new_session
        ↓
hidden one-time handoff ingestion
        ↓
dynamic workflow/integration context reloads only when needed
```

The full visible chat remains durable in ComfyUI-Pi's session store, but it is not replayed after every reset. The handoff is the compact continuity state. Large workflow JSON remains an on-demand file. Pi's built-in auto-compactor is disabled for the supervised RPC process when that RPC capability is available.

See [context-handoff.md](context-handoff.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Troubleshooting](troubleshooting.md) · [Next: Compatibility](compatibility.md)
<!-- DOC_NAV_FOOTER_END -->
