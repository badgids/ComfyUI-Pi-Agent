# Real Pi terminal inside ComfyUI

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar](sidebar-chat.md) · [Next: Local LLM servers and slash commands](local-llm-slash-commands.md)
<!-- DOC_NAV_END -->

The **Terminal** tab is the default Pi Agent interface view on platforms with a native PTY backend. It runs the actual interactive `pi` CLI inside ComfyUI instead of reconstructing Pi's interface from RPC events.

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

ComfyUI-Pi therefore connects the selected ComfyUI panel to a real Pi process through a controlling pseudo-terminal (PTY). The browser uses the bundled xterm.js renderer. There is no second user-facing web application and no separate terminal server.

```text
ComfyUI left sidebar or bottom panel
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

The Pi Agent interface has two views:

- **Terminal** — default when native PTY support is available. This is Pi's real interactive TUI.
- **Chat** — the structured ComfyUI chat renderer retained as a secondary/fallback interface.

The Chat view now recovers final text from Pi's authoritative `get_last_assistant_text` RPC when a provider produces an event stream that contains no usable visible text. It also records reasoning and tool activity separately.

In Chat settings, **Show reasoning** and **Show tool calls and tool activity** are both enabled by default. Disable either option to hide that information from the structured Chat display. Terminal mode follows Pi's own native rendering and Pi settings.


## Interface placement

ComfyUI settings provide **Pi Agent: Interface placement** with two choices:

- **Left sidebar** — the original Pi Agent location.
- **Bottom panel** — registers Pi Agent through ComfyUI's native `bottomPanelTabs` extension API in the same lower workspace used by ComfyUI terminal/log panels.

The same Terminal/Chat UI and the same supervised Pi session are used in either location. Refresh the ComfyUI browser page after changing placement so the extension registers only the selected location.

Collapsing either panel detaches only the ComfyUI-owned DOM host. It does **not** stop the supervised Pi PTY, close the live terminal WebSocket, dispose xterm, or create a new chat. The xterm instance continues receiving PTY output while the panel is hidden, so reopening the panel re-parents the same terminal DOM and immediately shows the exact screen/scrollback state from the ongoing conversation.

If the browser-side WebSocket drops while the panel is hidden, reopening first checks the lightweight terminal status endpoint and reconnects directly to the existing PTY. It does not run local-model readiness checks or call the terminal start path unless no live terminal exists. A reconnect after a dropped socket replays the backend terminal ring buffer before live output continues.

## Provider and Model controls

The same simple selectors remain directly below the interaction area:

```text
Provider  [ ... ]
Model     [ ... ]
```

Provider is always first. Model is always second.

For local providers, ComfyUI-Pi prepares the selected model before starting or restarting Pi. For an existing Terminal session, changing Provider or Model restarts the supervised Pi TUI with `--continue` in the same private terminal-session directory so Pi can continue that session under the new model.

Pi's current built-in `llama.cpp` provider requires a configured router URL even when the model is already loaded and reachable. ComfyUI-Pi passes the selected llama.cpp endpoint to every supervised Pi process as Pi's documented `LLAMA_BASE_URL` runtime setting (and `LLAMA_API_KEY` when a configured environment-variable reference supplies one). This makes the embedded Terminal use the same native provider path as a normal configured Pi CLI without requiring a second interactive `/login llama.cpp` inside ComfyUI.


## Terminal compatibility and focus

The terminal host does not take browser focus itself; clicks are forwarded to xterm's real input textarea so normal typing, Pi shortcuts, slash commands, and paste reach the PTY. The frontend accepts both modern xterm `onData`/`onResize` callbacks and the legacy EventEmitter form used by the bundled renderer.

Clipboard behavior follows a desktop terminal: **Ctrl/Cmd+C copies the current xterm selection**. When there is no selection, Ctrl+C is left untouched and continues to Pi as its normal interrupt key. **Ctrl/Cmd+V pastes text from the system clipboard** into the PTY.

Pi's current TUI wraps redraws in DEC synchronized-output mode. The bundled renderer predates that mode, so ComfyUI-Pi removes only the `2026` begin/end synchronization wrappers before rendering while preserving all visible ANSI content.

Terminal status exposes input/output byte counters. If Pi is running but no PTY output has arrived, the UI reports that distinction instead of claiming a healthy interactive terminal.

## Sparse dynamic guidance

Terminal mode does not re-enable Pi's global/project skill and context discovery. Pi is launched lean with discovered context files, extensions, skills, and prompt templates disabled. ComfyUI-Pi explicitly loads one small bridge extension.

For each real user prompt, that bridge:

1. observes the original input;
2. asks ComfyUI-Pi's deterministic router what task procedure or node-pack knowledge is relevant;
3. appends only that compact guidance to the system prompt for that turn;
4. leaves unrelated bundled skills and node-pack manuals unloaded.

The user's visible terminal input remains unchanged.

## In-place compaction and durable handoff in Terminal mode

The terminal bridge reports Pi's actual `getContextUsage()` values after completed agent work. ComfyUI-Pi watches those values using the configured 80–95% threshold range and 82.5% default, but **Pi remains the compaction authority**.

Pi's native compaction does not require a new session. It summarizes older context, appends a `CompactionEntry`, preserves recent messages from Pi's chosen keep boundary, rebuilds the active context from the summary plus those recent messages, and continues in the same session.

ComfyUI-Pi keeps its specialized continuity functions around that native mechanism:

1. before any Pi compaction (`manual`, `threshold`, or `overflow`), the bridge writes a bounded durable continuity checkpoint under ComfyUI user data;
2. the checkpoint keeps the complete active workflow referenced by path instead of embedding it;
3. the bridge returns control to Pi without cancelling `session_before_compact`;
4. Pi performs its normal in-place compaction and keeps the same session;
5. if the configured ComfyUI-Pi threshold is earlier than Pi's own reserve-token threshold, the bridge requests Pi's public `compact()` operation after the agent has fully settled;
6. the durable checkpoint remains an additive recovery/audit artifact; Pi's own `CompactionEntry` is the active memory used for the next turn.

No `/new` command is sent during compaction. Manual `/compact` remains Pi compaction, overflow recovery remains Pi's native recovery path, and both are checkpointed without replacing the session. A one-time marker left by an older reset-based ComfyUI-Pi build is still accepted only as backward-compatible recovery state.

## Platform support

The POSIX backend opens a PTY, launches a tiny single-threaded helper, and has that helper call `setsid()` plus `TIOCSCTTY` before it `exec`s Pi. Pi therefore becomes the session leader of a real **controlling terminal**, not merely a process with TTY-shaped stdin/stdout file descriptors. This is required by modern Pi TUI raw-mode, foreground-process-group, resize, and terminal-capability behavior. It works on Linux, WSL, and macOS environments where ComfyUI runs under POSIX Python.

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
