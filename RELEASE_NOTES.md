# Release notes — 0.1.9

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Changelog](CHANGELOG.md) · [Next: Project inventory](PROJECT_INVENTORY.md)
<!-- DOC_NAV_END -->

## 0.1.9 — Pi slash-command bridge and easy local LLM setup

- Added a ComfyUI-native slash-command picker to the Pi sidebar chat.
- Added host-side bridges for all currently documented Pi built-in slash-command names; RPC-supported operations map directly to Pi RPC while TUI-only credential/trust UI is handled transparently and safely.
- Added on-demand local-server discovery/configuration for llama.cpp, Ollama, LM Studio, vLLM, and other OpenAI-compatible servers.
- Added safe Pi `models.json` merging that preserves unrelated providers and stores environment-variable references instead of raw API secrets.
- Added llama.cpp runtime configuration through Pi's built-in provider and `LLAMA_BASE_URL`, plus explicit `/llama` list/load/unload/refresh/download router operations.
- Kept endpoint probing completely out of ComfyUI/plugin startup and out of normal LLM context.
- Kept Pi launch lean (`--no-context-files`, `--no-extensions`, `--no-skills`, `--no-prompt-templates`, `--no-themes`, `--no-session`) and preserved ComfyUI-Pi's preemptive handoff lifecycle.
- Added tests for the complete built-in command catalog, command parsing, local model discovery/configuration, secret handling, scoped-model launch configuration, and frontend controls.


## 0.1.8 — Fully navigable documentation

- Made the root README the guaranteed front door to every documentation branch.
- Rebuilt `docs/index.md` as the complete documentation map.
- Added top-and-bottom navigation to every user-facing guide.
- Added Home / Documentation / Previous / Next navigation so readers can drill down, move sideways, and climb back up.
- Added a complete linked index of every bundled Pi `SKILL.md`.
- Added navigation to example-workflow documentation and project/governance documents.
- Added automated documentation-graph tests so orphaned Markdown files and broken local links fail the test suite.



## Previous release — 0.1.7

### Two new lazy first-class node-pack integrations

ComfyUI-Pi now understands **ComfyUI-scene-camera-action** and **ComfyUI-MiniMax-H3-Turbo** out of the box without adding either pack's full guide to Pi's startup context. The integration registry remains host-side and matching modules are imported only when the user's instruction or current workflow contains a relevant pack name or public node ID.

### Scene Camera Action

ComfyUI-Pi recognizes `SceneNode`, `ActingNode`, and `DirectingNode`; understands the public `SCENE → ACTING` chain; validates generated/edited SceneState block/group JSON; plans human or car acting; and creates a conservative base previz graph. It deliberately does not fabricate the upstream frontend's recorded motion or camera-timeline serialization. Live `/object_info` schemas and the installed frontend remain runtime authority.

### MiniMax H3 Turbo

ComfyUI-Pi recognizes `MiniMaxH3TurboLoRA` and `MiniMaxH3TurboSampler`; understands the four-step `simple` scheduler starting profile, separate video/audio flow schedules, LoRA-strength and `low_vram` trade-offs, full/pruned bases, and H3 frame/shape constraints. Workflow creation starts from the user's installed upstream Turbo example rather than reconstructing the full H3 graph from stale assumptions.

### Context isolation

A Turbo request does not load the separate MiniMax H3 Director guide merely because both integrations contain the words “MiniMax H3.” Scene Camera Action and H3 Turbo likewise remain unloaded during unrelated writing, image, audio, tutorial, or production tasks. The existing deterministic small-model task router, sparse workflow digests, and preemptive handoff lifecycle remain unchanged.

The configurable handoff threshold remains **80%–95%**, with **82.5%** as the default.

---

## Previous release — 0.1.6

## Wider configurable handoff threshold

The preemptive handoff threshold remains **82.5% by default**, but the user-configurable range is now **80% through 95%**. This applies to backend clamping, sidebar controls, tests, and documentation.

## Small-local-model reliability layer

ComfyUI-Pi now moves more agent discipline out of the LLM and into deterministic host-side code.

- A short core operating contract tells Pi to stay on the current task, inspect before guessing, act when work was requested, preserve originals, use conservative tools, validate changes, and report evidence.
- A deterministic task classifier selects at most a few relevant ComfyUI-Pi bundled procedures. Pi does not have to decide which of the whole skill library it should read.
- A supplied workflow automatically selects `workflow-intelligence`, including terse follow-ups such as "fix it".
- Specific model procedures such as `qwen-image-edit` are preferred over unnecessary generic router context.
- Every turn gets a compact `CURRENT JOB (do not drift)` envelope with the exact instruction, task class, selected procedures, completion rule, and workflow-context rule.
- Selected procedure IDs participate in the hidden-context scope signature. When the task domain changes, ComfyUI-Pi clears stale hidden instructions with `new_session` and restores only bounded visible conversation plus newly relevant guidance.
- Task-procedure IDs are retained in continuity handoffs by ID and reloaded only if later work needs them.
- Fresh-model handoff summaries are structurally validated; weak summaries fall back to deterministic continuity generation.
- After reset, ComfyUI-Pi reads the bounded handoff host-side and injects it directly into the fresh context, so a small model does not have to successfully choose a file-read tool just to recover its work.
- The existing dynamic-context diagnostic node now reports both third-party integration routing and ComfyUI-Pi task-procedure routing.

The full procedure library, node-pack manuals, and complete workflow JSON remain excluded from startup context.

See `docs/small-model-reliability.md`.

---

## Previous release — 0.1.5

## Preemptive context handoff and reset

Long Pi sidebar sessions no longer rely on Pi's normal automatic compaction. ComfyUI-Pi now disables Pi auto-compaction through RPC when supported, prefers Pi's own `get_session_stats.contextUsage` current-context estimate (with a compatibility fallback for older builds), and performs a controlled handoff/reset around the configured threshold.

The default threshold is **82.5%**, with a supported user range of **80% to 85%**.

At the threshold ComfyUI-Pi:

1. saves the completed visible answer to its durable chat session;
2. creates a temporary handoff-source file on disk;
3. launches a separate fresh Pi RPC process to summarize continuity state, so the near-full session does not spend more context summarizing itself;
4. writes a bounded Markdown handoff (8,000 characters by default);
5. removes the temporary full handoff source;
6. resets the active Pi process with `new_session`;
7. silently tells the fresh context to read the handoff once;
8. verifies the handoff bootstrap and records the post-reset context pressure;
9. reloads workflow/node-pack knowledge lazily on later requests instead of replaying old hidden context.

The handoff is intentionally not a transcript. It keeps goals, constraints, decisions, completed work, artifact paths, workflow digest, blockers, and next actions. Large workflows, logs, books, screenplays, and node-pack manuals are referenced instead of embedded.

A deterministic fallback handoff is available if the isolated Pi summarizer cannot run.

The sidebar now shows context pressure and exposes the handoff threshold and size budget in Settings.

See `docs/context-handoff.md`.

---

## Previous release — 0.1.4

This release of **ComfyUI Pi Agent Production Suite** was created by **Alan D. Guice (Badgids)**.

## License changed to GPL-3.0

ComfyUI-Pi is now licensed under the **GNU General Public License version 3**.

The previous MIT license file and project metadata have been replaced. ComfyUI-Pi-owned bundled skills and integration metadata now identify GPL-3.0 as their license.

Third-party node packs, model weights, media, fonts, and other external assets keep their own copyrights and license obligations.

## Dynamic integration context

Node-pack knowledge is no longer injected into every Pi prompt merely because a supported pack is installed.

The new lazy integration router:

1. keeps a small integration registry host-side instead of injecting it into the model context;
2. checks the user message and optional current workflow;
3. matches public node IDs and explicit integration names;
4. imports only matching adapter modules;
5. injects a compact, task-targeted integration summary for normal matched requests;
6. loads the complete bundled skill only for explicit comprehensive tutorial/guide/deep-dive requests or an explicit caller request;
7. enforces per-integration and total context budgets;
8. injects nothing for unrelated requests.

The Pi RPC subprocess itself now starts with `--no-approve`, `--no-context-files`, `--no-extensions`, `--no-skills`, `--no-prompt-templates`, and `--no-themes`, and `--no-session`, preventing Pi's normal resource discovery or Pi-side transcript persistence from reintroducing unrelated startup context.

A clean import test verifies that the MiniMax H3 Director and WhatDreamsCost adapter modules are not loaded when `comfy_pi_agent.nodes` starts.

Sidebar workflow context is also lazy in 0.1.4: normal chat messages receive a bounded workflow digest, while the full active workflow JSON is stored in ComfyUI user data and made available for Pi to read on demand only when graph-level detail is required.

The standalone **Pi Agent Prompt** node now follows the same rule through its optional workflow input: the graph is used for integration routing, Pi receives a compact digest, and the full JSON is exposed through a temporary local context file only when deeper graph inspection is needed.

Stateful chat context is scope-aware. When the integration/project/workflow scope changes, ComfyUI-Pi uses Pi's `new_session` RPC command to clear hidden prior scope context, restores only a bounded visible transcript, and injects the new scope once.

## MiniMax H3 Director integration

The built-in MiniMax H3 Director integration is retained and now participates in the lazy router.

ComfyUI-Pi understands the public Director, Preview Override, Retake Stitch, and Enhance Prompt nodes; FL2VA/ref2VA model roles; MiniMax loader/VAE roles; reference limits; prompt rules; frame alignment; live preview; retakes; and safe workflow-editing boundaries.

## WhatDreamsCost-ComfyUI integration

Added first-class knowledge for:

```text
LTXDirector
LTXDirectorGuide
LTXDirectorCropGuides
LTXKeyframer
MultiImageLoader
LTXSequencer
SpeechLengthCalculator
LoadAudioUI
LoadVideoUI
```

The integration understands LTX Director 2 concepts including Prompt Relay, first/middle/last guide frames, custom audio, audio inpainting, IC-LoRA media, Retake Mode, timeline save/load, LTX's 8n+1 temporal rule, and the upstream distilled/GGUF example workflow paths.

New nodes:

```text
Pi Dynamic Integration Context
Pi WhatDreamsCost Status
Pi WhatDreamsCost Plan
Pi WhatDreamsCost Workflow
Pi Inspect WhatDreamsCost Workflow
```

Workflow creation starts from the **installed upstream pack's own current example workflow**. The adapter does not guess frontend-managed `timeline_data` or `widgets_values` indexes.

## Validation

The release contains new tests for:

- zero integration context for unrelated prompts;
- selective MiniMax loading;
- selective WhatDreamsCost loading;
- workflows containing both integrations;
- lazy module imports at startup;
- WhatDreamsCost node recognition;
- LTX Director workflow inspection;
- installed-example workflow selection;
- GGUF example selection;
- workflow-analyzer integration reports;
- lean Pi RPC startup flags;
- compact normal integration context versus explicit full-skill tutorial/deep-dive context;
- utility-node-specific lazy knowledge such as Multi Image Loader without loading the whole LTX Director guide.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Changelog](CHANGELOG.md) · [Next: Project inventory](PROJECT_INVENTORY.md)
<!-- DOC_NAV_FOOTER_END -->
