# Pi Agent sidebar chat

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Small local model reliability](small-model-reliability.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_END -->


The optional **Pi Agent** tab in ComfyUI now includes a normal AI chat interface. You can talk to Pi Agent directly without adding a node to the workflow.

## Enable the sidebar

1. Open ComfyUI settings.
2. Enable:

```text
Pi Agent: Show optional sidebar after restart
```

3. Reload or restart the ComfyUI frontend.
4. Open the **Pi Agent** tab in the left sidebar.

The sidebar is optional. All node-based tools continue to work when it is disabled.

## What the chat includes

The sidebar provides:

- normal user and assistant message bubbles;
- persistent chat sessions;
- a session picker;
- **New chat**, **Copy chat**, **Clear**, and **Delete** controls;
- a multiline message box;
- **Enter** to send;
- **Shift+Enter** to insert a new line;
- a **Stop** button while Pi is working;
- optional current-workflow context;
- optional project notes/context;
- optional project directory, provider, model, Pi executable, and timeout overrides.

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
- **New chat** creates a separate conversation.

A running Pi RPC process is kept for an active chat while the ComfyUI server stays running. After a full ComfyUI server restart, saved transcript history remains available, but a new Pi process is started when you send the next message.

## Pi is still optional

The sidebar itself loads even when Pi is not installed. It will show **Pi not configured** and explain what is missing.

Project compilers, workflow inspection, document export, tutorials, and other non-agent nodes can still work without Pi reasoning.

## No separate WebUI

This chat is part of the normal ComfyUI frontend. It does not start another web server or open a private external interface.


## Preemptive context handoff

Long sidebar conversations use ComfyUI-Pi's own continuity system instead of Pi's normal auto-compaction.

The Settings panel contains:

- **Preemptive context handoff and reset** — enabled by default;
- **Handoff threshold (%)** — default 82.5, allowed range 80 through 95;
- **Maximum handoff size** — default 8,000 characters.

The toolbar shows the latest measured context percentage. When the threshold is reached, the current answer is first saved to the visible chat history, then ComfyUI-Pi creates a compact handoff, resets Pi with `new_session`, ingests the handoff in the new context, and continues normally on the next message.

Handoffs are kept under ComfyUI user data. They contain working state and paths, not the complete transcript or full workflow JSON.

See [context-handoff.md](context-handoff.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Small local model reliability](small-model-reliability.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_FOOTER_END -->
