# Preemptive context handoff

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Dynamic integration context](dynamic-integration-context.md) · [Next: Project directory layout and asset organization](project-directory-layout.md)
<!-- DOC_NAV_END -->


Long Pi conversations can eventually approach the model's context-window limit. ComfyUI-Pi does not wait for Pi's normal automatic compaction to decide what to keep.

Instead, both sidebar modes use a **preemptive handoff and reset** system.

## Default behavior

The feature is enabled by default.

The normal trigger is:

```text
82.5% of the active model context window
```

The user may choose a value from **80% through 95%** in the Pi Agent sidebar settings.

ComfyUI-Pi prefers Pi's RPC `get_session_stats.contextUsage` values, which report Pi's current context estimate and active model context window. For older compatible Pi builds that do not expose `contextUsage`, ComfyUI-Pi falls back to the completed assistant message usage plus the model `contextWindow` from `get_state`. For usage math it prefers `totalTokens` and otherwise sums input, output, cache-read, and cache-write counters.

This is much more reliable than estimating the complete Pi context from the length of the visible chat.

## Pi threshold compaction is superseded

In structured Chat, when ComfyUI-Pi starts its supervised Pi RPC process, it sends:

```text
set_auto_compaction = false
```

ComfyUI-Pi then owns the long-session lifecycle. In Terminal mode, the explicit Pi bridge cancels `session_before_compact` only for Pi's normal `threshold` reason so ComfyUI-Pi can write its durable handoff first. Manual `/compact` remains native Pi behavior, and `overflow` compaction is left available as an emergency fallback.

If an older Pi build does not support the RPC auto-compaction command, structured Chat reports a warning instead of crashing ComfyUI.

## What happens at the threshold

After a completed Pi turn:

```text
Pi assistant result
        ↓
read exact usage + model context window
        ↓
context >= configured threshold?
        ↓ yes
create handoff source on disk
        ↓
start a separate fresh Pi summarizer process
        ↓
write bounded continuity handoff
        ↓
remove temporary handoff-source copy
        ↓
new_session on the active Pi process
        ↓
new session reads handoff exactly once
        ↓
HANDOFF_READY
        ↓
continue normal chat
```

The response that the user just received is not lost or replaced. The reset happens after that response has been saved in ComfyUI-Pi's durable sidebar transcript.


## Terminal-mode reset

The default real-Pi Terminal view does not translate the terminal into RPC. After every completed agent run, its bridge writes Pi's actual context usage and current session-file path to a tiny host-side state file. The ComfyUI-Pi terminal supervisor watches that state.

At the configured threshold it reads only user/assistant visible text from Pi's JSONL session, creates the bounded handoff, writes a one-time marker, and sends native Pi `/new` through the existing PTY. The browser terminal stays connected. On the next ordinary user task, the bridge reads the bounded handoff, appends it once to that turn's system prompt, and deletes the marker.

This preserves the real Pi CLI while keeping long-session continuity under ComfyUI-Pi control.

## Why a fresh summarizer is used

The near-full Pi session does **not** summarize itself.

Doing that would spend more tokens inside the context window that is already close to full.

Instead, ComfyUI-Pi launches a clean, isolated Pi RPC process using the same configured provider/model. That process reads a temporary source file and creates the handoff. The active near-full Pi conversation is not involved in handoff generation.

The fresh summarizer output is structurally checked before it is trusted. A handoff that is too short or does not contain the required objective/next-action information is rejected. If the isolated summarizer fails or produces an insufficient handoff, ComfyUI-Pi creates a deterministic fallback from the durable chat state, project notes, workflow digest, task-procedure IDs, and integration metadata.

## Handoff size

Default maximum:

```text
8,000 characters
```

The sidebar allows a range of 4,000 through 16,000 characters.

The handoff should be detailed enough to continue the task, but it is intentionally **not** a transcript.

It should preserve information such as:

- the primary user goal;
- non-negotiable constraints;
- important decisions;
- completed work;
- current project state;
- important filenames and artifact paths;
- active workflow role and digest;
- failures, blockers, and unresolved questions;
- the next useful actions;
- which dynamic integration knowledge or ComfyUI-Pi task procedures may need to be loaded later.

It should **not** embed:

- complete ComfyUI workflow JSON;
- giant logs;
- entire books or screenplays;
- model files;
- generated media;
- full third-party node-pack manuals;
- the complete chat transcript.

Those are referenced by path or compact digest instead.

## Where handoffs are saved

Handoffs are stored under the ComfyUI user-data directory:

```text
pi-agent/
└── handoffs/
    └── <chat-session-id>/
        ├── handoff-0001.md
        ├── handoff-0001.json
        ├── handoff-0002.md
        ├── handoff-0002.json
        └── latest.json
```

The temporary full source used by the isolated summarizer is deleted after the compact handoff is successfully written. The normal sidebar chat JSON remains the canonical visible transcript.

## Handoff ingestion

After `new_session`, ComfyUI-Pi reads the already bounded handoff file **host-side** and places that compact continuity state directly into one bootstrap prompt. A weak model therefore does not have to remember to call a file-read tool before it can recover the session. The durable handoff path is still included for inspection and verification.

The fresh context is instructed to internalize the handoff, avoid repeating it to the user, and acknowledge with `HANDOFF_READY`. Successful prompt delivery is sufficient to establish continuity because the handoff text itself is now in the new context; the acknowledgement is recorded separately as a diagnostic.

That bootstrap exchange is hidden from the normal visible chat history.

On the next real user message, the dynamic integration and task-procedure routers add only the knowledge currently needed. They do not replay every old integration guide or skill.

## Workflow context remains lazy

A large active ComfyUI workflow is never copied into the handoff.

The handoff includes:

- a compact workflow digest;
- the path of the on-demand workflow-context JSON when one exists.

Pi reads the complete workflow only when the next task actually requires graph-level detail.

## Sidebar status

The Pi Agent sidebar shows a small context indicator such as:

```text
Context 61.3%
```

Its tooltip shows the configured handoff threshold and handoff count.

After a handoff reset, the indicator reflects the new post-reset usage rather than continuing to display the old near-full percentage.

## What remains persistent

A context reset does not erase project state.

The following remain on disk:

- the visible sidebar transcript;
- project files;
- project manifests;
- workflows;
- references and bibles;
- generated media;
- tutorial files;
- previous compact handoff files.

Only Pi's in-memory conversation context is reset.

## Important limitation

The guard evaluates exact token usage at completed assistant-message boundaries. This is deliberate because resetting Pi in the middle of an active tool operation could corrupt the task state.

ComfyUI-Pi already reduces the risk of a single enormous turn by keeping workflow JSON and third-party integration guides out of ordinary prompts. Large graph details are made available by path and loaded only when needed.

A future release may add projected pre-turn pressure checks for exceptionally large pasted prompts while preserving the same safe handoff protocol.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Dynamic integration context](dynamic-integration-context.md) · [Next: Project directory layout and asset organization](project-directory-layout.md)
<!-- DOC_NAV_FOOTER_END -->
