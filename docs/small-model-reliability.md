# Small-model reliability

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi runtime and model-provider setup](pi-runtime.md) · [Next: Pi Agent sidebar chat](sidebar-chat.md)
<!-- DOC_NAV_END -->


ComfyUI-Pi is designed so the model does not need to be exceptionally large or clever to use the plugin correctly.

A small local model still has limits. No prompt can make a weak model equal to a much stronger model. ComfyUI-Pi therefore moves as much responsibility as practical **out of the LLM and into deterministic host-side code**.

## The basic rule

The model should not have to remember the whole plugin.

For each request, ComfyUI-Pi gives Pi only the information needed for the current job:

```text
user request
    ↓
host-side task classifier
    ↓
small operating contract
    ↓
1–3 relevant task procedures
    ↓
matching node-pack knowledge, only when needed
    ↓
compact workflow/project digest
    ↓
exact large files available by path on demand
```

The complete skill library is not inserted into the context window.

## Core operating contract

ComfyUI-Pi supplies a short stable contract that tells the agent to:

1. stay on the current task;
2. act instead of only describing a plan when work was requested;
3. inspect workflows, files, schemas, models, paths, and errors before guessing;
4. perform multi-step work in dependency order;
5. preserve originals, approved work, locked work, and user edits;
6. use conservative targeted tools instead of broad destructive operations;
7. validate every meaningful change;
8. avoid repeated questions when the answer can be discovered;
9. keep large material out of context until its exact contents are required;
10. use only dynamically selected procedures/integrations relevant to the job;
11. report completion with evidence instead of claiming success from assumption.

This contract is intentionally short. It provides behavioral guardrails without becoming context-window pollution.

## Deterministic task procedure routing

Pi's own automatic skill discovery is disabled in the supervised ComfyUI-Pi process so unrelated skills do not load at startup.

ComfyUI-Pi now selects its bundled task procedures itself.

Examples:

| User request | Procedure that may be loaded |
|---|---|
| "Repair this workflow" | `workflow-intelligence` |
| "Turn this book into a screenplay" | `story-to-screenplay` and `fountain-screenplay` |
| "Create the shot list" | `shot-planning` |
| "Compile a tutorial from these workflows" | `comfyui-tutorial-compile` |
| "Create a Qwen Image Edit workflow" | `qwen-image-edit` |
| "Use GGUF if the safetensors model is missing" | `gguf-model-resolution` |
| "Prepare this for Kdenlive" | `kdenlive-handoff` |
| "Compile the complete movie project" | `complete-production` |

At most a small number of matching procedures are loaded for a normal request.

A supplied workflow automatically selects the workflow-intelligence procedure even when the user says something very short such as:

```text
Fix it.
```

The model therefore does not have to infer that it needs workflow inspection rules.

## Current-job envelope

Each request gets a small explicit job description containing:

- the exact user instruction;
- a deterministic task class;
- selected procedures;
- a completion rule;
- whether an exact workflow is available on demand.

For example:

```text
CURRENT JOB (do not drift):
- User instruction: Repair this workflow.
- Task class: workflow
- Selected procedures: workflow-intelligence
- Completion rule: inspect the exact graph/live schemas, make only the requested change, validate it, and report unresolved items.
- Context rule: the workflow is available; read the exact graph only when graph-level details are required.
```

This helps small models keep a single objective instead of wandering into related tasks.

## Scope changes clear stale hidden guidance

The sidebar Pi process is stateful for responsiveness.

When the selected task procedures, integration, project context, or workflow scope changes, ComfyUI-Pi changes the scope signature. It then starts a fresh Pi conversation with `new_session`, restores only bounded user-visible history, and injects the newly relevant guidance.

This prevents a previous job's hidden instructions from confusing a later job.

For example:

```text
workflow repair
    ↓
workflow-intelligence loaded
    ↓
user switches to screenplay adaptation
    ↓
new scope detected
    ↓
old workflow-only hidden guidance removed
    ↓
story/screenplay procedures loaded
```

## Large workflows remain on demand

A weak model may be especially harmed by huge JSON graphs because important instructions become difficult to attend to.

ComfyUI-Pi therefore supplies:

- a bounded workflow digest in normal context;
- the exact full workflow in a temporary local file;
- an instruction to read that file only when graph-level details are needed.

The same policy is used for node-pack manuals and long project artifacts.

## Long-session handoffs

At **82.5% by default**, configurable from **80% through 95%**, ComfyUI-Pi writes a compact continuity handoff and resets Pi before normal compaction is allowed to take over.

The handoff preserves the current objective, constraints, decisions, artifacts, completed work, blockers, and next actions. It references large files instead of embedding them.

Task procedures and node-pack integrations are recorded by ID so they can be reloaded only when the next task actually needs them.

See [context-handoff.md](context-handoff.md).

## What this does not promise

A very small model can still misunderstand complex creative direction, make reasoning errors, or fail to use a tool correctly.

ComfyUI-Pi reduces those failure modes by making the workflow deterministic where possible. It does not hide errors or claim that model capability no longer matters.

For critical workflow edits, generated files, or project completion, ComfyUI-Pi's policy remains:

```text
inspect → act → validate → report evidence
```

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi runtime and model-provider setup](pi-runtime.md) · [Next: Pi Agent sidebar chat](sidebar-chat.md)
<!-- DOC_NAV_FOOTER_END -->
