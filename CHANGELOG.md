# Changelog

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Third-party notices](THIRD_PARTY_NOTICES.md) · [Next: Release notes](RELEASE_NOTES.md)
<!-- DOC_NAV_END -->

## 0.1.17 — controlling PTY terminal and selectable ComfyUI placement

- Fixed the real Pi terminal launch so POSIX Pi runs under a genuine controlling terminal through a tiny single-threaded PTY child that calls `setsid()` + `TIOCSCTTY` before `exec`. v0.1.16 provided TTY file descriptors but started a new session after opening the slave PTY, which could leave modern Pi TUI raw-mode/job-control initialization without a controlling terminal.
- Added a PTY regression test that proves the child owns the controlling terminal and can receive browser-style input.
- Fixed browser terminal focus by removing the outer host `tabindex`, explicitly focusing xterm on pointer interaction, and supporting both modern `onData`/`onResize` and legacy xterm event APIs.
- Added compatibility handling for Pi's DEC synchronized-output (`?2026`) redraw wrappers when using the bundled legacy xterm renderer.
- Added terminal input/output byte diagnostics so a running process with no PTY output is reported distinctly.
- Added **Pi Agent: Interface placement** with **Left sidebar** and **Bottom panel** choices. Bottom placement uses ComfyUI's native `bottomPanelTabs` extension API and the same Terminal/Chat implementation.
- Placement is applied on browser page load so only the selected Pi Agent location is registered.

## 0.1.16 — real Pi terminal sidebar and faithful output

- Added a PTY-backed **Terminal** view as the default Pi sidebar experience on POSIX platforms. It runs the actual interactive Pi CLI instead of reconstructing Pi's TUI through RPC.
- Vendored xterm.js under its MIT license for the browser terminal renderer; no extra npm/pip installation is required.
- Kept structured **Chat** as a secondary/fallback view and fixed false textless completions by falling back to Pi RPC `get_last_assistant_text` and the last assistant message.
- Structured Chat now records reasoning/thinking and tool activity separately. Both are visible by default and can be hidden independently from sidebar settings.
- Kept Provider → Model selectors beneath the interaction area. Terminal model/provider changes restart the supervised Pi CLI with `--continue` in the same private terminal session directory.
- Added one explicit Pi terminal bridge extension. It dynamically injects only the task/integration guidance needed for the current prompt while discovered context files, extensions, skills, and prompt templates remain disabled.
- Extended the preemptive handoff system to Terminal mode: Pi's bridge reports actual context usage, threshold auto-compaction is cancelled, a bounded durable handoff is written, native `/new` starts a fresh Pi session, and the handoff is injected exactly once on the next real task. Manual `/compact` and overflow recovery remain available.
- Added terminal capability/start/restart/stop/WebSocket routes and automatic fallback to structured Chat when a native PTY backend is unavailable.
- Added regression tests for terminal command construction, lazy terminal guidance, terminal handoff behavior, structured Chat final-text recovery, reasoning/tool capture, and default terminal UI state.

## 0.1.15 — llama.cpp sleeping-model wake fix and HTTP diagnostics

- Distinguished llama.cpp router `sleeping` from `unloaded`: only unloaded presets use `POST /models/load`.
- Wake sleeping llama.cpp models with the real routed `/tokenize` task that llama.cpp documents as an incoming task, using the user's remaining configured timeout budget.
- Added HTTP diagnostics that preserve the request method, endpoint, status, and llama.cpp response body instead of surfacing a bare `HTTP Error 400`.
- Added regression tests proving sleeping models do not call `/models/load`, wake probes can use the full caller-provided timeout, and no personal timeout value is hardcoded.


## 0.1.14 — llama.cpp router readiness contract correction

- Removed the invalid model-specific `/props?model=...&autoload=false` readiness request that could return HTTP 400 on current llama.cpp routers.
- Match llama.cpp's own router test lifecycle: request `/models/load`, poll `/models` until the selected preset is `loaded`, then verify routing with a lightweight model-targeted `POST /tokenize`.
- Keep sleeping/unloaded models non-ready until the router completes their load/wake transition.
- Continue using the user's configured chat timeout as the complete readiness budget; no personal timeout is hardcoded.
- Preserve the compact gear settings control and all existing lazy-context/local-provider behavior.

## 0.1.13 — Reliable llama.cpp wake/readiness

- Treat llama.cpp router `sleeping` as not-ready and explicitly wake it before Pi is allowed to send a prompt.
- Confirm the routed child server through model-specific `/props` after the router reports loaded, preventing stale-state races.
- Wait through single-model llama-server `/health` 503 loading responses.
- Pass the user's configured chat timeout through as the model-readiness budget; no personal timeout is hardcoded.
- Make Send wait for an in-progress model preparation request.
- Replace the visible Settings text button with a compact ComfyUI-style gear icon.

## 0.1.12 — llama.cpp router readiness and complete local catalogs

- Read llama.cpp router `/models` as the authoritative full preset catalog, including unloaded entries, before single-model fallback.
- Made explicit model refresh use the slower `?reload=1` path with a larger timeout and cached-catalog fallback.
- Wait for a selected llama.cpp router model to become ready before Pi RPC startup or live model switching.
- Probe Pi RPC readiness before the first chat command and include stderr/exit-code diagnostics on startup failure.
- Refresh stale local model lists when the sidebar chat is rendered, while retaining zero local-server probing at plugin import/startup.
- Fixed dark-mode Provider/Model dropdown option colors.
- Added tests proving the llama.cpp runtime has no static model catalog and uses discovered/supplied model IDs.


## 0.1.11 — Main chat provider/model switching

- Added Provider → Model selectors directly beneath the chat composer.
- Covered Pi's current complete built-in provider ID catalog while also surfacing custom/runtime providers.
- Filled cloud/provider models from Pi's live available-model RPC catalog and local models from each selected local host.
- Changed llama.cpp router discovery to list all routable non-failed models, including unloaded models, and best-effort load a selected unloaded model.
- Preserved active Pi context for ordinary live provider/model switches through RPC `set_model`.
- Kept endpoint overrides advanced/optional and retained zero startup probing.


## 0.1.10 — Simplified provider/model selection

- Replaced raw provider/model configuration fields with a normal provider dropdown and automatically populated model dropdown.
- Local providers now self-configure on selection using common defaults; endpoint override is advanced/optional.
- Unified llama.cpp with Pi's supported `models.json` local-provider path so discovered llama.cpp models are actually available to Pi RPC.
- Made `/model llama.cpp` and the other local provider names perform provider selection instead of ambiguous model-name lookup.
- Added repair for legacy v0.1.9 sessions with an endpoint URL stored as provider.
- Kept local probing opt-in by user action and outside LLM context.



## 0.1.9 — Slash commands and local LLM servers

- Added ComfyUI chat bridges for Pi's documented built-in slash commands.
- Added slash-command discovery/completion UI.
- Added explicit local-server detection and per-chat configuration for llama.cpp, Ollama, LM Studio, vLLM, and generic OpenAI-compatible servers, including llama.cpp router list/load/unload/refresh/download actions.
- Added safe Pi `models.json` merging and environment-variable API-key references.
- Preserved sparse startup context and lazy resource loading.


## 0.1.8 — Documentation navigation

- Added a complete documentation hub and bidirectional navigation across the documentation set.
- Added reachability and broken-link tests for all Markdown documentation.
- Linked every bundled Pi skill from the skills index and gave each skill a path back to its parent documentation.



## 0.1.7 — Scene Camera Action and MiniMax H3 Turbo integrations

- Added first-class lazy integration for `arturitu/ComfyUI-scene-camera-action` v0.3.0.
- Added recognition, planning, workflow creation, workflow inspection, API routes, documentation, profiles, and an original bundled procedure for `SceneNode`, `ActingNode`, and `DirectingNode`.
- Added SceneState validation for block/group staging JSON, spawn points, transforms, actor-aware layout rules, and conservative editing boundaries.
- Added first-class lazy integration for `Larryvrh/ComfyUI-MiniMax-H3-Turbo` v1.2.2.
- Added recognition, planning, installed-example workflow creation, workflow inspection, API routes, documentation, profiles, and an original bundled procedure for `MiniMaxH3TurboLoRA` and `MiniMaxH3TurboSampler`.
- Added Turbo guidance for the four-step `simple` scheduler baseline, separate video/audio sampling schedules, LoRA strength, `low_vram`, pruned/full bases, H3 frame-grid constraints, and joint AV preservation.
- Kept both integrations out of startup context and out of unrelated turns; adapters import only after explicit message/workflow matches.
- Tightened MiniMax H3 Director matching so generic H3 Turbo requests do not load Director knowledge.
- Added eight independently usable ComfyUI-Pi integration nodes and backend API parity.
- Preserved the 80%–95% preemptive handoff range and 82.5% default unchanged.

## 0.1.6 — Weak-model guidance and wider handoff range

- Expanded configurable preemptive handoff threshold range to 80%–95%; default remains 82.5%.
- Added a compact always-applicable ComfyUI-Pi operating contract for weak local models.
- Added deterministic host-side task classification and lazy bundled-procedure routing.
- Added explicit current-job envelopes and task-specific completion rules.
- Added procedure IDs to scope signatures and continuity handoffs so stale hidden guidance is cleared instead of accumulating.
- Updated the dynamic-context diagnostic node to show selected task procedures as well as third-party integrations.
- Added handoff structural validation and host-side fresh-context ingestion for weak models.
- Added small-model reliability documentation and automated routing tests.


## 0.1.5 — Preemptive context handoff

- Added a ComfyUI-Pi-owned context lifecycle for long sidebar sessions.
- Disables Pi's built-in auto-compaction over RPC when supported.
- Prefers Pi RPC `get_session_stats.contextUsage` for the current context estimate; falls back to assistant usage + model `contextWindow` on older compatible builds.
- Default preemptive handoff threshold is 82.5%, configurable from 80% through 85%.
- Creates a bounded Markdown continuity handoff with a separate fresh Pi process so the near-full session never summarizes itself.
- Falls back to a deterministic bounded handoff if the summarizer process fails.
- Resets the active Pi conversation with `new_session` and silently ingests the handoff once.
- Keeps complete workflow JSON out of the handoff; workflows remain available by on-demand context path and compact digest.
- Removes the temporary summarizer source copy after the durable handoff is created.
- Adds a sidebar context meter, threshold setting, handoff-size setting, and handoff count/status.
- Added context-handoff documentation and lifecycle tests.

## 0.1.4 — GPL-3.0, lazy context, and dual Director integrations

- Relicensed ComfyUI-Pi and its original bundled skills to GPL-3.0.
- Added a lazy integration registry/router so detailed node-pack knowledge is injected only for matching requests/workflows.
- Removed eager MiniMax H3 Director context from general Pi prompts and sidebar messages.
- Added first-class WhatDreamsCost-ComfyUI knowledge for LTX Director and its public utility nodes.
- Added WhatDreamsCost status, plan, workflow, and inspection nodes.
- Added `Pi Dynamic Integration Context` diagnostics.
- Added workflow-analyzer reports for WhatDreamsCost graphs.
- Added installed-upstream-example selection for LTX Director distilled, GGUF, custom-audio, and FFLF workflows.
- Added detailed integration and context-management documentation.
- Started supervised Pi RPC with context/resource discovery disabled (`--no-context-files`, `--no-skills`, `--no-extensions`, `--no-prompt-templates`, `--no-themes`, `--no-session`, `--no-approve`).
- Changed normal matched integration requests to compact, task-targeted context; full bundled skills are reserved for explicit comprehensive guide/tutorial/deep-dive requests.
- Added scope-aware RPC session resets so hidden integration context does not linger after the relevant node-pack/project/workflow scope changes.
- Replaced repeated full active-workflow injection in sidebar chat with a compact digest plus an on-demand local workflow context file.
- Added utility-node-specific lazy context for WhatDreamsCost nodes.
- Added lazy-import, context-size, Pi launch, and integration routing tests.

## 0.1.3 — MiniMax H3 Director interoperability

- Added MiniMax H3 Director detection, planning, inspection, and installed-example workflow creation.
- Added FL2VA/ref2VA, prompt, reference, frame-grid, VAE, preview, retake, and Enhance Prompt knowledge.
- Added MiniMax H3 Director documentation and bundled skill.

## 0.1.2 — Native Pi Agent sidebar chat

- Replaced the status-only optional sidebar with a standard ComfyUI-native AI chat interface.
- Added persistent chat sessions stored under ComfyUI user data.
- Added normal selectable text, per-message Copy controls, whole-chat copy, multiline paste support, Enter-to-send, and Shift+Enter for new lines.
- Added New chat, Clear, Delete, and Stop controls.
- Added optional current-workflow JSON context, project notes, project directory, provider, model, executable, and timeout overrides.
- Added backend chat session routes and persistent per-chat Pi RPC clients.
- Added chat documentation and automated tests.

## 0.1.1 — Explicit project asset directories

- Replaced broad project folders with explicit top-level directories for stories, screenplays, production bibles, mood boards, reference sheets, storyboards, scene and shot plans, prompts, ComfyUI workflows, generated media, editorial media, NLE projects, tutorials, quality control, delivery, and archives.
- Added `START_HERE.md`, Markdown and DOCX directory guides, `asset-catalog.json`, and `directory-map.json` to every generated project.
- Added a plain-language `README.md` to every generated directory and subdirectory.
- Added starter story, screenplay, mood-board, reference-sheet, storyboard, prompt, workflow, scene-list, and shot-list files in their permanent labeled locations.
- Added tests that verify every generated directory is labeled and every major asset category has an obvious location.

## 0.1.0 — First release

- Added safe ComfyUI custom-node entrypoint with no required third-party Python packages.
- Added Pi executable discovery and strict JSONL RPC client.
- Added workflow analysis, validation, and conservative structural repair.
- Added ComfyUI model inventory, family profiles, and safetensors/GGUF-aware resolver.
- Added prompt packages and multimodal reference manifests.
- Added Fountain creation, parsing, validation, screenplay breakdown, and shot-list planning.
- Added complete project directory and documentation compiler.
- Added ComfyUI-native tutorial compiler for one or more workflows.
- Added Markdown, DOCX, and JSON export.
- Added Kdenlive-first NLE handoff package.
- Added optional ComfyUI sidebar, disabled by default.
- Added original bundled Pi skills, examples, documentation, and tests.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Third-party notices](THIRD_PARTY_NOTICES.md) · [Next: Release notes](RELEASE_NOTES.md)
<!-- DOC_NAV_FOOTER_END -->
