# Preemptive same-session context compaction and durable handoff

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Dynamic integration context](dynamic-integration-context.md) · [Next: Project directory layout and asset organization](project-directory-layout.md)
<!-- DOC_NAV_END -->


Long Pi conversations eventually approach the active model's context window. ComfyUI-Pi handles that pressure **before** the hard limit while preserving Pi's current session.

The old reset-based design that sent `new_session`/`/new` for context pressure has been retired. Current builds use Pi's native **same-session compaction** plus an additive durable continuity checkpoint.

## Defaults

The guard is enabled by default.

```text
threshold: 82.5%
allowed range: 80%–95%
maximum handoff text: 8,000 characters
allowed handoff range: 4,000–16,000 characters
```

ComfyUI-Pi prefers Pi's exact/current context-usage data. Structured Chat prefers RPC `get_session_stats.contextUsage`; Terminal uses Pi's bridge `getContextUsage()` values. Compatibility fallbacks use model context-window and completed usage counters when exact usage is unavailable.

## What the durable checkpoint is for

The handoff is an **additive recovery/audit artifact**, not a replacement Pi session. It preserves bounded working state such as:

- the user's objective and non-negotiable constraints;
- decisions and completed work;
- current/in-progress work;
- important file, workflow, model, and artifact identifiers;
- blockers and unresolved questions;
- concrete next actions;
- compact workflow/project context and IDs of procedures/integrations that can be reloaded on demand.

Large workflows, logs, manuals, media, books, and model files are referenced by path/digest rather than copied into the handoff.

Handoffs remain under ComfyUI user data:

```text
pi-agent/
└── handoffs/
    └── <sidebar-session-id>/
        ├── handoff-0001.md
        ├── handoff-0001.json
        └── latest.json
```

## Terminal threshold sequence

The normal Terminal path is deliberately early enough that Pi does not run all the way to 100% before compacting:

```text
Pi completes a turn
        ↓
turn_end reports context usage
        ↓
usage >= configured threshold?
        ↓ yes
write + verify durable checkpoint
        ↓
append hidden same-session compaction anchor
        ↓
mark one compaction request in flight
        ↓
ctx.compact() immediately
        ↓
session_before_compact
        ↓
use/verify bounded checkpoint as continuity summary
        ↓
Pi writes its normal CompactionEntry in the SAME session
        ↓
session_compact verifies session file + session id + handoff ingestion
        ↓
continue current task in the same Pi session
```

The visible status at the threshold is expected to say that the checkpoint was saved and compaction is happening **now**. It must not say that it is merely waiting while context continues toward 100%.

### Lifecycle fallbacks

`turn_end` is the normal preemptive request boundary. `compactionRequested` is set before `ctx.compact()` so later lifecycle hooks cannot launch a duplicate request.

`agent_end` remains a **prepare-only fallback** for the unusual case where usable context pressure was not available at `turn_end`. It does not start a second compaction that could race Pi's own post-agent checks. If that prepared state still requires a manual same-session request after Pi settles, `agent_settled` performs the one fallback request.

Pi's native `session_before_compact`/`session_compact` events remain authoritative for the actual compaction transaction.

## Manual and overflow compaction

Manual `/compact` remains Pi-native. ComfyUI-Pi uses the same bounded durable checkpoint/continuity rules around the lifecycle.

Overflow recovery remains Pi's emergency path. It is not a reason to deliberately wait until 100%; the configured preemptive threshold should normally compact first.

No context-pressure path intentionally sends `/new`, calls `new_session`, forks the conversation, or selects another saved Pi session.

## Exact same-session verification

Terminal continuity records the active Pi session file and session ID around compaction. A changed session identity is treated as a continuity failure rather than silently accepting a different conversation as the compacted result.

The hidden anchor identifies the exact pre-compaction boundary inside the current Pi branch. `session_compact` verifies that the durable handoff was ingested into the resulting compaction entry. Compaction IDs suppress duplicate automatic continuation turns.

If the Pi **process** crashes independently of compaction, Terminal recovery is a different mechanism: ComfyUI-Pi reopens the exact recorded `pi-sessions/*.jsonl` file when possible. Process recovery must not be confused with context-pressure compaction.

## Structured Chat

Structured Chat also uses a durable checkpoint followed by Pi's native in-place compaction. Pi RPC automatic threshold compaction is disabled when supported so the ComfyUI-Pi guard can own the earlier configured threshold without allowing two competing threshold requests.

This is separate from **hidden-scope changes**. When the selected integration/project/workflow scope changes, structured Chat may intentionally issue Pi RPC `new_session` and rehydrate bounded visible history so stale hidden instructions disappear. That scope-isolation operation is not context-window compaction.

## Handoff generation quality

Where a model-produced bounded summary is used, ComfyUI-Pi validates that it contains useful continuity state before trusting it. A deterministic fallback can be built from durable visible chat/project/workflow/procedure metadata when summarization fails.

The checkpoint is intentionally bounded. It is not a transcript and it does not embed large referenced artifacts.

## Workflow context remains lazy

A large active ComfyUI workflow is not copied into every checkpoint. The continuity state carries a compact digest and, when applicable, a safe local path to the serialized workflow. Pi reads the complete graph only when the next task genuinely needs graph-level detail.

## Sidebar status

The Pi Agent context indicator reports measured context pressure and configured threshold. After same-session compaction, subsequent usage reflects Pi's compacted context while the saved sidebar transcript and project artifacts remain durable on disk.

## What remains persistent

Same-session compaction does not delete project state. These remain available:

- the sidebar's durable visible transcript;
- the active Pi session and its saved JSONL history;
- project files and manifests;
- workflows and references;
- generated media and tutorial files;
- prior durable handoff/checkpoint files.

## Safety rule

ComfyUI-Pi creates the checkpoint at a completed-turn boundary rather than interrupting an arbitrary tool operation. The guard is preemptive because it watches exact context pressure and requests compaction as soon as the configured threshold is reached at that safe boundary.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Dynamic integration context](dynamic-integration-context.md) · [Next: Project directory layout and asset organization](project-directory-layout.md)
<!-- DOC_NAV_FOOTER_END -->
