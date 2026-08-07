# Architecture

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Troubleshooting](troubleshooting.md) · [Next: Compatibility](compatibility.md)
<!-- DOC_NAV_END -->


## Layers

1. ComfyUI nodes in `comfy_pi_agent/nodes.py`.
2. Shared services for workflows, models, Fountain, projects, tutorials, NLE, DOCX, Pi RPC, and PTY terminal supervision.
3. Optional HTTP/WebSocket routes in `comfy_pi_agent/routes.py`.
4. Optional ComfyUI frontend extension in `web/pi_agent.js`, including the bundled xterm.js terminal renderer.
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

The supervised Pi RPC process disables automatic project context files, extension discovery, skill discovery, prompt-template discovery, theme discovery, and project trust for that run. The real Terminal process similarly disables automatic context/extension/skill/prompt discovery but explicitly loads `pi/terminal-bridge.ts`. The integration registry remains host-side.

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


## Sidebar runtime modes

On POSIX systems the default sidebar path is `browser xterm.js → ComfyUI WebSocket → OS PTY → real interactive pi`. Structured Chat remains `browser messages → ComfyUI route → Pi JSONL RPC`. Both share provider preparation, lazy integration routing, and handoff storage. See [pi-terminal.md](pi-terminal.md).

## Context lifecycle

Both sidebar modes use a host-controlled context lifecycle:

```text
Pi usage + get_state contextWindow
        ↓
82.5% default threshold (configurable 80–95%)
        ↓
bounded Markdown handoff on disk
        ↓
Chat: active Pi RPC new_session
Terminal: native Pi /new through PTY
        ↓
hidden one-time handoff ingestion
        ↓
dynamic workflow/integration context reloads only when needed
```

The structured Chat transcript remains durable in ComfyUI-Pi's session store, while Terminal uses Pi's own session JSONL under a per-sidebar terminal directory. The handoff is the compact continuity state. Large workflow JSON remains an on-demand file. Pi's RPC auto-compactor is disabled when supported; the terminal bridge cancels threshold-triggered auto-compaction while leaving manual `/compact` and overflow recovery intact.

See [context-handoff.md](context-handoff.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Troubleshooting](troubleshooting.md) · [Next: Compatibility](compatibility.md)
<!-- DOC_NAV_FOOTER_END -->
