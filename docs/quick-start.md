# Quick start

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Installation](installation.md) · [Next: Node reference](node-reference.md)
<!-- DOC_NAV_END -->


## Use Pi without a node

Enable the optional Pi Agent interface in ComfyUI settings, choose **Left sidebar** or **Bottom panel** placement, then reload the frontend. On POSIX/WSL systems the **Terminal** tab is the default and renders Pi's real interactive TUI; **Chat** is the structured fallback/secondary view. The session toolbar provides New, JSON Load, JSON Save, Rename, and Delete actions. Provider and Model selectors stay in the lower footer. See [sidebar-chat.md](sidebar-chat.md).

## Step 1: Status

Add **Pi Agent Status**. Leave the executable field empty. Queue the node.

- `available: true` means the `pi` command was found.
- `available: false` means project, tutorial, document, and workflow tools still work, but Pi reasoning is unavailable.

## Step 2: Model inventory

Add **Pi Model Inventory**. Queue it. The output is a structured list of model filenames registered by ComfyUI.

## Step 3: Analyze a workflow

Paste a saved workflow JSON into **Pi Analyze Workflow**. Large workflows are easier to provide by entering the file path.

Read the report before repairing anything.

## Step 4: Create a prompt package

Use **Pi Prompt Package**. Choose the modality and model family. State requested changes, preservation rules, and negative constraints separately.

## Step 5: Create a project

Use **Pi Compile Project**. An empty output directory places the project under ComfyUI's user directory. An explicit directory uses the path you selected.

Open the generated `START_HERE.md` first. The project creates separate top-level directories for the story, screenplay, production bibles, mood boards, reference sheets, storyboards, scene and shot plans, prompts, workflows, media, tutorials, and Kdenlive files. Every folder has its own `README.md`.

## Step 6: Compile a tutorial

Provide one workflow or a JSON list of workflow paths to **Pi Compile Tutorial**. Load the generated `Tutorial_Controller.json` inside ComfyUI.

## Check MiniMax H3 Director integration

When `ComfyUI-MiniMaxH3-Director` is installed, add **Pi MiniMax H3 Director Status** to see whether ComfyUI-Pi found the pack, its registered nodes, and its installed example workflows. You can also open the Pi Agent interface and ask `Explain this MiniMax H3 Director workflow.` No Pi node is required for sidebar chat.


## Check WhatDreamsCost integration

When `WhatDreamsCost-ComfyUI` is installed, add **Pi WhatDreamsCost Status** to see registered nodes and installed example workflows. In the Pi Agent interface you can attach/use the active workflow context and ask `Explain this LTX Director workflow.`

## See what context Pi will load

Use **Pi Dynamic Integration Context** with context preview disabled to see which node-pack guides match without loading the full guide. See [dynamic-integration-context.md](dynamic-integration-context.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Installation](installation.md) · [Next: Node reference](node-reference.md)
<!-- DOC_NAV_FOOTER_END -->
