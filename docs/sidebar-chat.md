# Pi Agent sidebar chat

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Small local model reliability](small-model-reliability.md) · [Next: Real Pi terminal](pi-terminal.md)
<!-- DOC_NAV_END -->


The optional **Pi Agent** tab gives you two ways to work with Pi without adding a node: **Terminal** (the real Pi interactive TUI and the default on supported platforms) and **Chat** (the structured ComfyUI chat view).

## Enable the sidebar

1. Open ComfyUI settings.
2. Enable:

```text
Pi Agent: Show optional sidebar after restart
```

3. Reload or restart the ComfyUI frontend.
4. Open the **Pi Agent** tab in the left sidebar.

The sidebar is optional. All node-based tools continue to work when it is disabled.

## What the sidebar includes

The sidebar provides:

- a default **Terminal** view backed by the real interactive Pi CLI;
- a secondary **Chat** view with normal user and assistant message bubbles;
- Pi reasoning and tool activity visible by default in Chat, with settings to hide either;
- persistent chat sessions;
- a session picker;
- **New session**, **Copy chat**, **Clear**, and **Delete** controls;
- a multiline message box;
- **Enter** to send;
- **Shift+Enter** to insert a new line;
- a **Stop** button while Pi is working;
- optional current-workflow context;
- optional project notes/context;
- **Provider** then **Model** dropdowns directly beneath the active Terminal/Chat interaction area;
- optional project directory, Pi executable, local endpoint, and timeout overrides in Settings.

## Copy and paste

Chat text is deliberately rendered as normal selectable text.

You can:

- drag the mouse over part of any message and copy it;
- use Ctrl+C or Cmd+C after selecting text;
- click **Copy** on one message;
- click **Copy chat** to copy the whole transcript;
- paste text into the message box with Ctrl+V or Cmd+V;
- paste multi-line prompts, scripts, Fountain text, JSON, notes, and error logs.

The plugin does not disable text selection inside chat messages.

## Current workflow context

The **Include the current ComfyUI workflow with each message** option is enabled by default in the chat panel.

When enabled, ComfyUI-Pi sends a compact structural digest of the current workflow. The complete workflow JSON is stored temporarily in ComfyUI user data and is made available to Pi by path, so Pi reads the full graph only when the current request needs graph-level details. This lets you ask things such as:

```text
Explain this workflow.

Why is this node failing?

Turn this workflow into a complete tutorial.

What models are missing from this graph?

Help me convert this into a Qwen Image Edit workflow.
```

Turn the option off when the current workflow is unrelated to the conversation or when you do not want to send a large graph to Pi.

## Project context

The Settings area contains two project fields.

### Project directory

This is optional. When provided, Pi runs with that directory as its project working directory.

Leave it blank to use the normal ComfyUI user-data location.

### Project notes/context

Use this for short project information that should accompany a request, for example:

```text
This is Scene 12 of the workshop sequence.
Badgids must keep the same black suit and brown fedora.
The approved storyboard is version 4.
```

Do not paste secrets such as passwords or API keys into project notes.

## Chat history

Chat history is saved as JSON under ComfyUI user data in the Pi Agent chat-session directory. This lets the sidebar restore the conversation after the panel is closed or the browser page is reloaded.

- **Clear** keeps the chat session but removes its messages.
- **Delete** removes that saved chat session.
- **New session** creates a separate conversation/terminal session.

Structured Chat keeps a Pi RPC process for an active chat. Terminal mode instead runs a real interactive Pi process through a PTY and keeps Pi sessions in a per-sidebar-session directory under ComfyUI user data. After a server restart, Pi can continue that terminal session.

## Pi is still optional

The sidebar itself loads even when Pi is not installed. It will show **Pi not configured** and explain what is missing.

Project compilers, workflow inspection, document export, tutorials, and other non-agent nodes can still work without Pi reasoning.

## No separate WebUI

This chat is part of the normal ComfyUI frontend. It does not start another web server or open a private external interface.

## Pi slash commands and local models

Type `/` in the composer to open the Pi command picker. ComfyUI-Pi bridges Pi's built-in interactive slash-command names to RPC/host operations so commands such as `/model`, `/session`, `/tree`, `/compact`, and `/copy` work from the ComfyUI sidebar instead of being sent to the LLM as ordinary text.

Directly beneath the active Terminal/Chat interaction area are two selectors, in this order:

1. **Provider**
2. **Model**

The Provider selector includes Pi's current built-in provider IDs, local model hosts, Pi's default/current model, and custom providers visible in Pi's configuration/runtime catalog. Selecting a hosted provider filters the Model selector to models Pi actually reports as available for that provider. This avoids a second hardcoded model list becoming stale.

Selecting llama.cpp, Ollama, LM Studio, vLLM, or another OpenAI-compatible local host queries that host's own model list, registers the reported usable models with Pi, and fills the Model selector. llama.cpp router mode reads the full live `/models` catalog, including configured presets that are currently unloaded. Selecting an unloaded or sleeping preset requests a load, waits for `/models` to report that exact preset as `loaded`, and verifies routing with a lightweight `/tokenize` call before Pi starts, so the first chat prompt cannot race a large local-model load. The implementation never hardcodes the user's llama.cpp model names.

Local endpoints are hidden in **Settings → Local model host — advanced → Advanced: custom endpoint** because the common loopback defaults work for normal installations. Opening an existing Pi Agent Chat refreshes its selected local host so stale saved dropdown data is replaced by the host's current catalog; this happens only when the chat UI is rendered, not when the plugin is imported at ComfyUI startup. The explicit Refresh button asks a llama.cpp router to re-read its preset source with a longer timeout. Provider/model catalogs are UI/runtime data and are not injected into ordinary LLM conversation context. Expanded Provider/Model menus have explicit dark-mode styling so native options remain readable. The toolbar uses the same compact gear-style settings affordance as the rest of ComfyUI instead of a large Settings text button. When a local model is still preparing, Send waits for the active model-preparation operation rather than racing it.

A built-in provider may appear in Provider while Model is empty. That means Pi does not currently report an authenticated/configured model for that provider; configure its Pi credentials/provider normally, then reopen or refresh the model selector.

See [Local LLM servers and Pi slash commands](local-llm-slash-commands.md).

## Preemptive context handoff

Long sidebar conversations use ComfyUI-Pi's own continuity system instead of Pi's normal auto-compaction.

The Settings panel contains:

- **Preemptive context handoff and reset** — enabled by default;
- **Handoff threshold (%)** — default 82.5, allowed range 80 through 95;
- **Maximum handoff size** — default 8,000 characters.

The toolbar shows the latest measured context percentage. In structured Chat, the reset uses Pi RPC `new_session`. In Terminal mode, ComfyUI-Pi writes the same bounded durable handoff, sends native Pi `/new` through the PTY, and injects the handoff exactly once on the next real task. See [Real Pi terminal](pi-terminal.md).

Handoffs are kept under ComfyUI user data. They contain working state and paths, not the complete transcript or full workflow JSON.

See [context-handoff.md](context-handoff.md).

### Sleeping llama.cpp router models

A llama.cpp router can keep a model entry in `sleeping` state after idle sleep. ComfyUI-Pi treats that differently from `unloaded`: only an unloaded preset is sent to `/models/load`. A sleeping model is woken by a lightweight routed `/tokenize` task, because llama.cpp defines real incoming tasks as the wake trigger. The wait uses the current chat's configured **Timeout in seconds** value; no personal timeout value is hardcoded. HTTP failures include the method, endpoint, status, and response body for troubleshooting.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Small local model reliability](small-model-reliability.md) · [Next: Real Pi terminal](pi-terminal.md)
<!-- DOC_NAV_FOOTER_END -->
