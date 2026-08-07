# Dynamic integration context

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: MiniMax H3 Turbo integration](minimax-h3-turbo.md) · [Next: Preemptive context handoff](context-handoff.md)
<!-- DOC_NAV_END -->


ComfyUI-Pi supports detailed knowledge for third-party node packs without stuffing all of that knowledge into Pi's context window at startup.

## The rule

**No node-pack guide is injected at startup.**

ComfyUI-Pi keeps a very small **host-side** integration registry. That registry is used by the Python router and is not copied into Pi's model context at startup. It contains identifiers such as:

- integration name;
- public ComfyUI node IDs;
- a few matching phrases;
- the module and skill file to load if needed.

The detailed Python adapter remains unloaded until a request matches. Even after a match, normal requests receive the adapter's compact task-targeted context only. The complete `SKILL.md` is reserved for explicit comprehensive-guide/tutorial/deep-dive requests or an explicit diagnostic load.

## Pi itself also starts lean

The supervised Pi RPC subprocess is launched with:

```text
--no-approve
--no-context-files
--no-extensions
--no-skills
--no-prompt-templates
--no-themes
--no-session
```

So node-pack context is not being hidden somewhere else by Pi's normal resource discovery. ComfyUI-Pi controls what specialized knowledge is added to each request.

`--no-session` prevents Pi from creating its own persistent hidden chat transcript for the supervised subprocess. ComfyUI-Pi stores the visible sidebar conversation itself.

### Turn-scoped specialized context

Pi RPC is stateful while a process is alive, so simply injecting a guide lazily once is not enough: that text could otherwise remain in later unrelated turns. ComfyUI-Pi therefore hashes the current specialized scope (integration context, bounded project context, and compact workflow digest). When the scope changes, it sends Pi's `new_session` RPC command, rehydrates only a bounded user-visible transcript, and adds the new scope once. Hidden old integration text is not replayed.

When the scope has not changed, ComfyUI-Pi keeps the existing in-memory Pi conversation and does not inject the same integration guide again on every turn.

## What causes an integration to load?

An integration can be selected in three ways:

1. **The user names it.**
   - Example: `Explain this LTX Director workflow.`
   - Example: `Make this MiniMax H3 Director workflow use ref2VA.`
2. **The attached/current workflow contains one of its public node IDs.**
   - Example: `LTXDirector` activates WhatDreamsCost; `SceneNode` activates Scene Camera Action; `MiniMaxH3TurboSampler` activates H3 Turbo.
   - Example: `MiniMaxH3DirectorCS` activates the MiniMax H3 Director integration.
3. **A user explicitly calls an integration-specific ComfyUI-Pi node.**

If none of those conditions is true, no integration knowledge is added to the Pi request.

A match also does **not** automatically mean "load every detail about this pack." The adapter selects the parts relevant to the request. For example, asking about `MultiImageLoader` adds its utility-node guidance without automatically adding every LTX Director/Prompt Relay detail. Asking about a MiniMax retake adds retake guidance without requiring the whole bundled Director guide.

## Why this matters

A long node-pack guide can contain thousands of tokens. Loading every guide for every chat message would:

- waste context-window space;
- make small questions unnecessarily expensive;
- distract the model with unrelated node rules;
- increase the chance of mixing rules from unrelated model families;
- make long production sessions hit context limits earlier.

The dynamic router avoids that.

## Example

User message:

```text
Write a short character biography.
```

Loaded integration context:

```text
none
```

User message:

```text
Explain the LTX Director node in the workflow I have open.
```

Loaded integration context:

```text
whatdreamscost-comfyui
```

User message:

```text
Convert this MiniMax H3 Director workflow from FL2VA to ref2VA.
```

Loaded integration context:

```text
minimax-h3-director
```

A workflow that deliberately contains nodes from both packs may load both guides for that request.

## Large active workflows are also lazy

When sidebar chat includes the current workflow, ComfyUI-Pi does not inject the entire UI workflow JSON into every request. It creates a bounded workflow digest containing useful facts such as node types, model candidates, missing nodes, issues, and detected integrations. The complete workflow JSON is saved to a local context file under ComfyUI user data. Pi receives the path and is instructed to read that file only when the task actually requires graph-level detail.

This matters because frontend-heavy Director workflows can be very large. A user can keep the workflow attached for accurate routing without spending tens of thousands of context tokens on every conversational turn.

## Context budget

The registry sets hard character budgets:

```text
maximum per integration: 14,000 characters
maximum combined integration context: 24,000 characters
```

These are guardrails, not a target. Most requests should use less.

The router truncates integration material rather than allowing a large collection of guides to consume the whole Pi context. Normal matched requests are expected to be far below these hard caps.

The complete bundled skill is automatically considered only for explicit requests such as a comprehensive tutorial, complete integration guide, or deep dive.

## Live schemas still win

The built-in knowledge explains how the node pack is intended to work. It is not a replacement for the user's installed version.

Before changing a workflow, ComfyUI-Pi should still inspect:

- the active workflow;
- live ComfyUI `/object_info` schemas;
- registered node classes;
- installed model files;
- the installed node pack's own current example workflows.

This is especially important for frontend-heavy nodes such as LTX Director and MiniMax H3 Director because their serialized timeline state may change between releases.


## ComfyUI-Pi task procedures are lazy too

The same context rule applies to ComfyUI-Pi's own bundled procedures. Pi starts with `--no-skills`; ComfyUI-Pi classifies the current request host-side and loads only a small matching set such as `workflow-intelligence`, `story-to-screenplay`, `qwen-image-edit`, or `kdenlive-handoff`. The complete procedure library is never preloaded.

The dynamic-context diagnostic node reports both matching integrations and selected task procedures. See [small-model-reliability.md](small-model-reliability.md).

## `Pi Dynamic Integration Context`

This diagnostic node lets a user see what the router would match.

Inputs:

- `message`
- `workflow_json_or_path`
- `include_context_preview`

With the preview disabled it returns only the routing decision, so it does not load the full skill text.

With the preview enabled it performs the same lazy load Pi would use and shows the resulting context.

## Adding another node pack later

A new integration should add:

1. a small entry in `data/integrations/registry.json`;
2. a profile under `data/integrations/`;
3. an adapter module under `comfy_pi_agent/integrations/`;
4. a detailed skill under `pi/bundled-skills/`;
5. tests.

Do not add the new pack's entire guide to the global Pi prompt.


## Preemptive handoffs

Dynamic integration routing and preemptive context handoff work together. A handoff records only the active integration IDs and the task state. It does not copy complete integration guides into the handoff. After the reset, detailed pack knowledge is injected again only when the next request actually needs it. See [context-handoff.md](context-handoff.md).


## Additional first-class lazy integrations in 0.1.7

```text
scene-camera-action
minimax-h3-turbo
```

These follow the same policy: a tiny registry entry exists host-side, but their Python adapter and detailed guide are not imported/injected until a matching message, matching workflow node ID, or explicit integration node requires them. A Turbo-specific request does not match the Director adapter merely because both names contain MiniMax H3.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: MiniMax H3 Turbo integration](minimax-h3-turbo.md) · [Next: Preemptive context handoff](context-handoff.md)
<!-- DOC_NAV_FOOTER_END -->
