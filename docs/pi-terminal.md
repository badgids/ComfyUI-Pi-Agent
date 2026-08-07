# Real Pi terminal in the ComfyUI sidebar

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar](sidebar-chat.md) · [Next: Local LLM servers and slash commands](local-llm-slash-commands.md)
<!-- DOC_NAV_END -->

The **Terminal** tab is the default Pi Agent sidebar view on platforms with a native PTY backend. It runs the actual interactive `pi` CLI inside ComfyUI instead of reconstructing Pi's interface from RPC events.

## Why Terminal is the default

Pi's own interactive interface already knows how to render:

- assistant text while it streams;
- thinking/reasoning blocks;
- built-in and extension tool calls;
- tool output and errors;
- slash-command completion and interactive selectors;
- `/model`, `/settings`, `/tree`, `/resume`, `/llama`, and the rest of Pi's interactive commands;
- queued steering/follow-up input;
- Pi's footer, model, context, and session information.

ComfyUI-Pi therefore connects the browser sidebar to a real Pi process through a pseudo-terminal (PTY). The browser uses the bundled xterm.js renderer. There is no second user-facing web application and no separate terminal server.

```text
ComfyUI sidebar
      ↓
xterm.js terminal renderer
      ↓
ComfyUI-Pi WebSocket route
      ↓
OS pseudo-terminal (PTY)
      ↓
real interactive `pi` process
```

## Terminal and Chat views

The sidebar has two views:

- **Terminal** — default when native PTY support is available. This is Pi's real interactive TUI.
- **Chat** — the structured ComfyUI chat renderer retained as a secondary/fallback interface.

The Chat view now recovers final text from Pi's authoritative `get_last_assistant_text` RPC when a provider produces an event stream that contains no usable visible text. It also records reasoning and tool activity separately.

In Chat settings, **Show reasoning** and **Show tool calls and tool activity** are both enabled by default. Disable either option to hide that information from the structured Chat display. Terminal mode follows Pi's own native rendering and Pi settings.

## Provider and Model controls

The same simple selectors remain directly below the interaction area:

```text
Provider  [ ... ]
Model     [ ... ]
```

Provider is always first. Model is always second.

For local providers, ComfyUI-Pi prepares the selected model before starting or restarting Pi. For an existing Terminal session, changing Provider or Model restarts the supervised Pi TUI with `--continue` in the same private terminal-session directory so Pi can continue that session under the new model.

## Sparse dynamic guidance

Terminal mode does not re-enable Pi's global/project skill and context discovery. Pi is launched lean with discovered context files, extensions, skills, and prompt templates disabled. ComfyUI-Pi explicitly loads one small bridge extension.

For each real user prompt, that bridge:

1. observes the original input;
2. asks ComfyUI-Pi's deterministic router what task procedure or node-pack knowledge is relevant;
3. appends only that compact guidance to the system prompt for that turn;
4. leaves unrelated bundled skills and node-pack manuals unloaded.

The user's visible terminal input remains unchanged.

## Preemptive handoff in Terminal mode

The terminal bridge reports Pi's actual `getContextUsage()` values after completed agent work. ComfyUI-Pi watches those values using the same configured 80–95% threshold range and 82.5% default used by structured Chat.

When the threshold is reached:

1. ComfyUI-Pi reads only the visible user/assistant text needed from Pi's session JSONL;
2. writes the bounded durable handoff under ComfyUI user data;
3. keeps the complete active workflow referenced by path instead of embedding it;
4. sends Pi's native `/new` command through the PTY;
5. stores a one-time handoff marker;
6. on the next real user task, the bridge injects that bounded handoff once and removes the marker.

The bridge cancels Pi's normal **threshold-triggered** auto-compaction so the durable handoff happens first. Manual `/compact` remains a real Pi command. Pi's overflow recovery is also left available as an emergency fallback for a single unexpectedly huge turn.

## Platform support

The first terminal backend uses the standard POSIX PTY API, so it works on Linux, WSL, and macOS environments where ComfyUI runs under POSIX Python.

When native PTY support is unavailable, the Terminal tab is disabled and ComfyUI-Pi automatically falls back to structured Chat. This must never stop ComfyUI or the node pack from loading.

Native Windows ConPTY can be added as another backend without changing the browser protocol.

## Security boundary

The terminal launches Pi with an argument array, not a shell command string. It uses the configured Pi executable discovery order and does not hardcode personal paths, model IDs, or user-specific timeouts.

The PTY belongs to the ComfyUI server process. Browser interaction is exposed only through ComfyUI-Pi's registered ComfyUI routes.

## Related guides

- [Pi Agent sidebar](sidebar-chat.md)
- [Pi runtime and provider setup](pi-runtime.md)
- [Local LLM servers and slash commands](local-llm-slash-commands.md)
- [Dynamic integration context](dynamic-integration-context.md)
- [Preemptive context handoff](context-handoff.md)
- [Small local model reliability](small-model-reliability.md)

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar](sidebar-chat.md) · [Next: Local LLM servers and slash commands](local-llm-slash-commands.md)
<!-- DOC_NAV_FOOTER_END -->
