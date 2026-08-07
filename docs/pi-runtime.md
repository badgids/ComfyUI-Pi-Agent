# Pi runtime

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Node reference](node-reference.md) · [Next: Small local model reliability](small-model-reliability.md)
<!-- DOC_NAV_END -->


## What Pi provides

Pi supplies the LLM runtime, configured model/provider access, and conversational session engine. ComfyUI-Pi deliberately does **not** let its supervised RPC subprocess auto-discover unrelated Pi skills, extensions, prompt templates, themes, or project context files. ComfyUI-Pi supplies workflow/project services and injects only the integration knowledge needed for the current request.

## Discovery order

1. Explicit node input.
2. `PI_AGENT_EXECUTABLE`.
3. `pi` found on `PATH`.

No personal location is searched.

## RPC protocol

The plugin launches Pi with an argument array and `--mode rpc`. It writes one JSON object per line to standard input and reads one JSON object per line from standard output.

### Lean RPC startup

ComfyUI-Pi starts its Pi subprocess with discovery disabled for resources that would otherwise add unrelated startup context:

```text
--no-approve
--no-context-files
--no-extensions
--no-skills
--no-prompt-templates
--no-themes
--no-session
```

This means the supervised Pi process does not automatically consume project `AGENTS.md`/`CLAUDE.md`, discovered skills, discovered extensions, prompt templates, or themes just because they exist on the machine. `--no-approve` also prevents project-local Pi resources from becoming trusted implicitly for this non-interactive RPC run.

`--no-session` means Pi does not separately persist a hidden RPC transcript; the ComfyUI-Pi sidebar's own visible chat-session store remains the source of chat history.

These flags affect only the Pi subprocess launched by ComfyUI-Pi. They do not delete or modify the user's normal Pi configuration or files.

The client:

- correlates the prompt response with an ID;
- collects `text_delta` events;
- treats `message_end` as authoritative when available;
- waits for `agent_settled`;
- aborts after the configured timeout;
- does not use `shell=True`;
- disables Pi's built-in automatic compaction through RPC when supported;
- prefers Pi's `get_session_stats.contextUsage` current-context estimate for the context guard, with assistant usage + model `contextWindow` as a compatibility fallback.

## Model providers

The sidebar exposes **Provider** then **Model** directly beneath the chat box. The Provider selector contains Pi's current built-in provider catalog, supported local hosts, and custom providers visible in Pi's runtime/configuration. Hosted-provider models are read from Pi's own `get_available_models` RPC snapshot; the plugin does not maintain a second hardcoded cloud-model catalog. Selecting another already-available hosted model uses Pi RPC `set_model`, preserving the active Pi process and context.

For local use, selecting llama.cpp, Ollama, LM Studio, vLLM, or the generic OpenAI-compatible entry explicitly probes only that host, reads all models the host reports as selectable, and safely merges those IDs into Pi's supported `models.json`. llama.cpp router discovery uses the full live `/models` catalog so configured-but-unloaded presets are included. If the chosen router model is not ready, ComfyUI-Pi requests the load and waits for router readiness **before** spawning Pi. Explicit Refresh can use `/models?reload=1` with a longer timeout to re-read presets. Local catalog changes restart only the supervised Pi RPC process because Pi must reload `models.json`. Common endpoints are automatic; the endpoint field lives under **Settings → Local model host — advanced** and is optional.

Pi RPC startup itself has a readiness probe. ComfyUI-Pi sends `get_state` before accepting the first real chat turn. If Pi terminates because a provider/model/configuration cannot initialize, the surfaced error includes the Pi process exit code and recent stderr output, making the root cause diagnosable instead of returning only a generic early-exit message.

No local endpoint is probed at plugin startup. Provider/model UI catalogs are not copied into ordinary LLM prompts. Do not paste provider keys into a ComfyUI workflow. A built-in provider can appear in the Provider selector before it has usable models; the Model selector is populated only with models Pi currently reports as available/authenticated.

See [Local LLM servers and Pi slash commands](local-llm-slash-commands.md) for setup and the embedded slash-command bridge.

## Missing Pi

The plugin still loads. Workflow analysis, project compilation, tutorial compilation, Fountain, DOCX, and NLE nodes remain usable.

## Small-model operating guidance

ComfyUI-Pi does not rely on Pi's disabled automatic skill discovery to teach a local model how to perform the current job. A deterministic host-side task router selects at most a few relevant bundled procedures and injects them only for the matching task. A short core operating contract tells the model to stay on the current task, inspect before guessing, act when work was requested, preserve originals, validate changes, and report completion with evidence.

The selected task-procedure IDs are part of the sidebar scope signature. If the task domain changes, stale hidden procedures are cleared with `new_session` and only the newly relevant guidance is restored.

See [small-model-reliability.md](small-model-reliability.md).

## Integration context and context-window use

ComfyUI-Pi does not preload its MiniMax H3 Director, WhatDreamsCost, Scene Camera Action, or MiniMax H3 Turbo guides into every Pi session.

Before an individual prompt is sent, the dynamic integration router looks at the user request and, when supplied, the current workflow. Ordinary prompts receive no node-pack context. A matching integration gets only a compact, task-targeted context summary by default. The full bundled `SKILL.md` is loaded only for explicit deep-guide/tutorial requests or when a caller deliberately asks for it.

Sidebar chat also prevents old hidden integration context from lingering forever in Pi's stateful RPC conversation. ComfyUI-Pi computes a signature from the active integration/project/workflow scope. When that scope changes it sends Pi's supported `new_session` RPC command, then rehydrates only a bounded copy of the visible user/assistant transcript and injects the newly relevant scope once. Normal turns with an unchanged scope continue in the same in-memory Pi conversation.

See [dynamic-integration-context.md](dynamic-integration-context.md).


## Preemptive handoff instead of Pi auto-compaction

For stateful sidebar conversations, ComfyUI-Pi owns context lifecycle instead of relying on Pi's built-in compaction summary. The default trigger is **82.5%** of the model context window and can be adjusted between 80% and 95%.

When the threshold is reached, ComfyUI-Pi creates a bounded continuity handoff using a separate fresh Pi process, structurally validates that handoff, resets the active Pi process with `new_session`, then reads the bounded file host-side and injects that continuity state directly into the fresh context. This avoids depending on a weak model to decide to call a file-read tool after reset. Large workflows and node-pack manuals stay referenced by path or dynamic integration ID instead of being copied into the handoff.

See [context-handoff.md](context-handoff.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Node reference](node-reference.md) · [Next: Small local model reliability](small-model-reliability.md)
<!-- DOC_NAV_FOOTER_END -->
