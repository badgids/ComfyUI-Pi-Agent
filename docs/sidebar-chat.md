# Pi Agent Terminal and Chat interface

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Small local model reliability](small-model-reliability.md) · [Next: Real Pi terminal](pi-terminal.md)
<!-- DOC_NAV_END -->


The optional **Pi Agent** interface gives you two ways to work with Pi without adding a node: **Terminal** (the real Pi interactive TUI and the default on supported platforms) and **Chat** (the structured ComfyUI chat view).

## Enable the interface

1. Open ComfyUI settings.
2. Enable `Pi Agent: Enable interface after restart`.
3. Choose **Pi Agent: Interface placement** → **Left sidebar** or **Bottom panel**.
4. Refresh the ComfyUI browser page.
5. Open **Pi Agent** in the selected panel.

The interface is optional. All node-based tools continue to work when it is disabled.

## Left sidebar or bottom panel

Placement is handled by ComfyUI itself. **Left sidebar** uses ComfyUI's sidebar-tab API. **Bottom panel** uses the native `bottomPanelTabs` extension API. The plugin registers only the selected location on page load, so the same Pi session is not duplicated in two panels.

Changing placement requires a browser refresh so ComfyUI can rebuild its registered extension panels.

## Terminal and Chat are tabs

**Terminal** and **Chat** are normal tab controls rather than button-styled actions.

- **Terminal** is default when the POSIX controlling-PTY backend is available.
- **Chat** is the structured RPC view and the fallback when a native terminal backend is unavailable.

Terminal uses Pi's own TUI, slash commands, menus, footer, streaming, reasoning/tool presentation, and keyboard behavior. Chat renders normal user/assistant messages and can independently show or hide reasoning and tool activity.

## Session toolbar

The session row contains a saved-session selector followed by same-sized icon buttons:

- **+** — create a new sidebar/Pi session;
- **folder** — load/import a saved sidebar session JSON file;
- **save** — export the current sidebar session as JSON;
- **pencil** — rename the selected session;
- **trash** — delete the selected saved sidebar session.

There is no separate **Copy chat** button and no **Clear** button. Individual Chat messages remain selectable/copyable, and deleting a saved session is the explicit destructive session action.

The JSON export/import format preserves the sidebar Chat document and safe configuration fields. Import creates a **new local session ID** instead of overwriting an existing session. The exported JSON is not a portable copy of the private Terminal `pi-sessions/*.jsonl` history; exact Terminal continuity on the same machine is provided by the Terminal session directory and recovery system described in [pi-terminal.md](pi-terminal.md).

Renaming updates the sidebar session title immediately. A Pi process that is already running keeps the name it was launched with until that Terminal process is restarted/reopened.

## Sending and stopping Chat messages

Structured Chat uses the composer keyboard:

- **Enter** sends;
- **Shift+Enter** inserts a new line;
- **Stop** is shown only while structured Chat is actively processing.

There is intentionally no Send button. Terminal input goes directly to Pi's real terminal and is not sent through the Chat composer.

## Copy and paste

Chat text is rendered as normal selectable text. Select any part of a message and use Ctrl/Cmd+C. Each message can also expose its own copy affordance. Paste ordinary text, multi-line prompts, scripts, Fountain, JSON, notes, and logs into the Chat composer normally.

Terminal follows desktop-terminal clipboard behavior: Ctrl/Cmd+C copies only when xterm has a selection; without a selection it remains Pi's interrupt key. Paste is forwarded to the PTY.

## Provider and Model footer

The lower control area is always ordered:

1. **Provider**
2. **Model**

In Terminal view the xterm area expands to consume the remaining panel height above the status/provider/model footer. The status line reports **Connected to Pi terminal.** for a live connection.

Hosted models come from Pi's live provider/model catalog. Local llama.cpp, Ollama, LM Studio, vLLM, and generic OpenAI-compatible selections query the selected host on demand; ComfyUI-Pi does not hardcode the user's model names. llama.cpp router mode reads the live `/models` catalog, wakes/loads the selected preset as needed, waits for that exact preset to report loaded, and performs a routed `/tokenize` readiness check before Pi starts.

## Settings on smaller screens

The gear opens project, workflow-context, local-host, timeout, reasoning/tool visibility, and context-compaction settings. The Settings panel has its **own vertical scrollbar** when the available sidebar/panel height is too small to show every setting. Horizontal overflow is suppressed so controls remain usable on narrow displays.

## Current workflow context

**Include the current ComfyUI workflow** is enabled by default. Normal Pi context receives a compact structural digest rather than an entire large workflow. The full serialized graph is stored temporarily under ComfyUI user data and made available by path when exact graph-level work is required.

For live tutorial/documentation screenshot capture, the visible browser also supplies a serialized copy of the active workflow to the Playwright screenshot broker. A separate capture page loads that copy into the same running ComfyUI frontend; the visible user's graph is not replaced just to take the screenshot.

## Project context

**Project directory** is optional and selects Pi's project working directory. Leave it blank to use normal ComfyUI user data. **Project notes/context** should contain only short working information, never passwords, API keys, or access tokens.

## Saved Terminal recovery

Each sidebar session owns a private Terminal directory and Pi session history under ComfyUI user data. Collapsing the interface keeps the supervised Pi PTY and xterm state alive. If the browser WebSocket drops, reopening reconnects to the existing terminal when possible. If Pi itself exits unexpectedly and a saved Pi JSONL session exists, the supervisor reopens the **exact recorded session file** when available rather than guessing the newest global session.

## Preemptive same-session compaction

The Settings panel exposes:

- **Preemptive context handoff** — enabled by default;
- **Handoff threshold (%)** — default 82.5, allowed range 80 through 95;
- **Maximum handoff size** — default 8,000 characters.

At the completed-turn threshold, ComfyUI-Pi writes a bounded durable checkpoint and then requests Pi's native compaction **in the same session**. Terminal mode does not send `/new` for compaction. The current task/session identity is verified around the compaction boundary, and the durable handoff becomes continuity input for Pi's normal `CompactionEntry` lifecycle. See [context-handoff.md](context-handoff.md) and [pi-terminal.md](pi-terminal.md).

Structured Chat also uses in-place compaction with a durable checkpoint rather than the old reset/bootstrap protocol. Scope changes for hidden integration guidance may still deliberately use Pi RPC `new_session`; that is separate from context-pressure compaction.

## Pi is still optional

The interface can load even when Pi is not installed. It reports the missing Pi runtime while non-agent workflow inspection, project compilers, document export, tutorials, and related nodes remain available.

## No separate WebUI

The interface is part of the normal ComfyUI frontend. It does not start a second user-facing web server.

## Related setup

- [Real Pi terminal](pi-terminal.md)
- [Pi runtime and model-provider setup](pi-runtime.md)
- [Local LLM servers and Pi slash commands](local-llm-slash-commands.md)
- [Preemptive context handoff](context-handoff.md)

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Small local model reliability](small-model-reliability.md) · [Next: Real Pi terminal](pi-terminal.md)
<!-- DOC_NAV_FOOTER_END -->
