# Architecture

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Troubleshooting](troubleshooting.md) · [Next: Compatibility](compatibility.md)
<!-- DOC_NAV_END -->


## Layers

1. ComfyUI nodes in `comfy_pi_agent/nodes.py`.
2. Shared services for workflows, models, Fountain, projects, tutorials, NLE, DOCX, Pi RPC, and PTY terminal supervision.
3. Optional HTTP/WebSocket routes in `comfy_pi_agent/routes.py`.
4. Optional ComfyUI frontend extension in `web/pi_agent.js`, including the bundled xterm.js terminal renderer and selectable left-sidebar/native-bottom-panel placement.
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

On POSIX systems the Terminal path is `browser xterm.js → ComfyUI WebSocket → controlling OS PTY (`setsid` + `TIOCSCTTY` helper) → real interactive pi`. The UI can be registered in either ComfyUI’s left sidebar or its native bottom panel. Structured Chat remains `browser messages → ComfyUI route → Pi JSONL RPC`. Both share provider preparation, lazy integration routing, and handoff storage. See [pi-terminal.md](pi-terminal.md).

## Context lifecycle

Context pressure and hidden-scope isolation are two different lifecycle operations. Context pressure uses Pi's native **same-session compaction**; it does not create a new Pi session:

```text
Pi context usage
        ↓
82.5% default threshold (configurable 80–95%)
        ↓
write + verify bounded durable checkpoint
        ↓
Terminal turn_end: immediately request ctx.compact()
Structured Chat guard: request native in-place compaction
        ↓
Pi session_before_compact / CompactionEntry / session_compact
        ↓
verify same session + durable continuity
        ↓
continue work in the compacted session
```

The structured Chat transcript remains durable in ComfyUI-Pi's session store, while Terminal uses Pi's own session JSONL under a private per-sidebar-session directory. Large workflow JSON remains an on-demand file and handoffs/checkpoints stay bounded. Manual `/compact` and Pi overflow recovery keep Pi's native same-session lifecycle.

A **structured Chat hidden-scope change** is separate: when integration/project/workflow guidance changes, Chat may intentionally use Pi RPC `new_session`, rehydrate bounded visible history, and inject the newly relevant hidden scope. That operation removes stale hidden instructions; it is not context-window compaction.

See [context-handoff.md](context-handoff.md) and [dynamic-integration-context.md](dynamic-integration-context.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Troubleshooting](troubleshooting.md) · [Next: Compatibility](compatibility.md)
<!-- DOC_NAV_FOOTER_END -->
