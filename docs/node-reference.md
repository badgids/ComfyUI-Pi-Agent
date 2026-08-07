# Node reference

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Quick start](quick-start.md) · [Next: Pi runtime and model-provider setup](pi-runtime.md)
<!-- DOC_NAV_END -->


All nodes appear under the **Pi Agent** category.

## Pi Agent Status

Finds Pi from an explicit path, `PI_AGENT_EXECUTABLE`, or `PATH`.

Outputs:

- status JSON;
- plain-language message.

## Pi Agent Prompt

Starts Pi in RPC mode, sends a prompt, collects streaming events, and waits for `agent_settled`.

Inputs include provider, model, project directory, executable, and timeout. An optional
`workflow_json_or_path` input lets the normal Pi Agent Prompt node recognize and reason
about the supplied workflow without requiring a pack-specific node. Provider credentials
remain in Pi's configuration.

When a workflow is supplied, ComfyUI-Pi injects only a compact structural digest. The full
workflow is written to a temporary ComfyUI user-data context file and Pi is told to read it
only when graph-level detail is actually needed. Matching node-pack guidance is loaded by
the same lazy integration router used by sidebar chat.

## Pi Analyze Workflow

Accepts a UI workflow or API prompt graph. Reports nodes, links, input files, model-like filenames, execution order, missing registered classes, issues, and recognized first-class integrations such as MiniMax H3 Director, WhatDreamsCost-ComfyUI, Scene Camera Action, and MiniMax H3 Turbo.

## Pi Validate Workflow

Returns a Boolean and a full report. Strict mode treats warnings as validation failure.

## Pi Repair Workflow

Performs conservative structural repairs only. It does not replace creative nodes or guess missing models.

## Pi Model Inventory

Reads ComfyUI's registered model categories through `folder_paths`.

## Pi Model Resolver

Ranks installed filenames for a requested family and preferred format. A result is a candidate, not proof of architecture compatibility.

## Pi Model Profiles

Returns the bundled capability registry for image, edit, speech, music, and audio families.

## Pi Prompt Package

Creates a typed package with prompt, modality, model family, references, preservation rules, and negative constraints.

## Pi Reference Asset

Creates a versioned reference manifest for character sheets, voices, music, audio, mood boards, storyboards, environments, props, or visual bibles.

## Pi Image Workflow Plan

Creates a model-family-aware plan for Qwen Image, Qwen Image Edit, Krea 2, Krea 2 Edit, FLUX.2 Klein, or Z-Image. It records references, component requirements, format preference, speed, quality, and validation steps.

## Pi Qwen Image Edit Plan

Specialized edit plan that emphasizes image-aware conditioning, reference roles, preservation rules, and GGUF companion validation.

## Pi Krea 2 Edit Plan

Specialized Krea 2 edit plan that records Raw, Turbo, or Identity Edit behavior and the requirement for compatible edit LoRA and adapter nodes.

## Pi MiniMax H3 Director Status

Detects the separately installed `ComfyUI-MiniMaxH3-Director` pack through live public node registration and normal custom-node discovery. Reports the four supported public Director node IDs, installed example workflows, source license, and integration profile.

## Pi MiniMax H3 Director Plan

Creates a Director-aware generation plan. `auto` uses FL2VA when no actual reference media is requested and ref2VA when image, video, or audio references are requested. It checks the H3 frame grid, trained-duration guidance, reference limits, prompt format, preview, Enhance Prompt, and retake options.

## Pi MiniMax H3 Director Workflow

Creates a Director workflow from the **installed upstream pack's own example workflow**. It does not ship or fabricate a copy of the GPL workflow. When the upstream pack is missing, it returns a clear unavailable result instead of guessing schemas or frontend timeline state.

## Pi Inspect MiniMax H3 Director Workflow

Recognizes the Director, Preview Override, Retake Stitch, and Enhance Prompt nodes and checks Director-specific requirements such as `CLIPLoader` type `minimax`, FL2VA/ref2VA checkpoint roles, video/audio VAE roles, serialized reference counts, and safe editing boundaries.

Read [MiniMax H3 Director integration](minimax-h3-director.md).

## Pi Scene Camera Action Status

Detects the separately installed `ComfyUI-scene-camera-action` pack, its three public nodes, available staging presets, and the upstream `scene-staging-builder` skill. Detection is lazy and does not import the pack into ComfyUI-Pi at startup.

## Pi Scene Camera Action Plan

Creates a previz plan for staging, human/car acting, duration, and optional camera directing. It preserves the upstream 4–15 second Acting duration range and identifies whether the scene should be generated, loaded from a preset, or edited from existing SceneState JSON.

## Pi Scene Camera Action Workflow

Creates a conservative `SceneNode → ActingNode → DirectingNode` base graph using only the public socket contract. It deliberately leaves frontend-managed scene editing, recorded actor motion, and camera-cut timeline state to the installed upstream widgets instead of fabricating unknown serialization.

## Pi Inspect Scene Camera Action Workflow

Recognizes `SceneNode`, `ActingNode`, and `DirectingNode`; checks chain connections and actor settings; and validates SceneState block/group JSON when available. SceneState checks include IDs, numeric transforms, spawn-point fields, supported block/group types, and obvious ground-placement problems.

Read [Scene Camera Action integration](scene-camera-action.md).

## Pi MiniMax H3 Turbo Status

Detects `ComfyUI-MiniMax-H3-Turbo`, its `MiniMaxH3TurboLoRA` and `MiniMaxH3TurboSampler` nodes, and its installed example workflows.

## Pi MiniMax H3 Turbo Plan

Creates a Turbo-aware T2V, I2V, or first/last-frame plan with a minimum of four steps, `simple` scheduler guidance, LoRA strength, and the upstream `low_vram` sharpness/VRAM trade-off.

## Pi MiniMax H3 Turbo Workflow

Creates from the **installed upstream Turbo example workflow**, preserving the official H3 joint video/audio pipeline. For I2V or FLF it attaches `LoadImage` nodes only by confirmed named `MiniMaxH3ImageToVideo` sockets and marks the placeholder images for replacement before execution. It does not fabricate the complete H3 graph when the validated upstream baseline is unavailable.

## Pi Inspect MiniMax H3 Turbo Workflow

Checks that both Turbo nodes are present, the custom Turbo sampler feeds `SamplerCustomAdvanced`, the LoRA sits in the model path, and the H3 scheduler/joint-AV structure is appropriate. It warns about stock-sampler four-step audio problems, scheduler mismatches, and other unsafe substitutions instead of silently rewriting them.

Read [MiniMax H3 Turbo integration](minimax-h3-turbo.md).

## Pi Dynamic Integration Context

Reports both lazily matched third-party integration context and the small set of ComfyUI-Pi task procedures selected for the current request. Context preview remains optional.


Shows which optional node-pack integrations match a message and/or workflow. With context preview off, only the tiny registry is consulted. With preview on, matching integration modules and their detailed skills are loaded lazily. Unrelated requests return no integration context.

## Pi WhatDreamsCost Status

Detects the separately installed `WhatDreamsCost-ComfyUI` pack using its public node IDs and normal custom-node discovery. Reports registered nodes and installed upstream example workflows.

## Pi WhatDreamsCost Plan

Creates an LTX/WhatDreamsCost-aware plan for Director, custom-audio, two-stage FFLF, or three-stage FFLF workflows. It records safetensors/GGUF preference plus Prompt Relay, custom-audio, IC-LoRA, and Retake requirements.

## Pi WhatDreamsCost Workflow

Creates a workflow by copying the closest **installed upstream example workflow**. GGUF requests prefer the upstream GGUF example. The node does not fabricate the large LTX Director timeline serialization when the pack is unavailable.

## Pi Inspect WhatDreamsCost Workflow

Recognizes all public WhatDreamsCost node IDs, checks LTX Director-specific loader/timeline concerns, records the present features it can safely infer, and warns rather than guessing frontend-managed timeline state.

Read [WhatDreamsCost-ComfyUI integration](whatdreamscost-comfyui.md) and [Dynamic integration context](dynamic-integration-context.md).

## Pi Audio Workflow Plan

Creates a plan for ACE-Step 1.5, Qwen3-TTS, or Stable Audio 3. It records mode, duration, language, reference audio, components, and workflow steps.

## Pi Character Sheet Plan

Creates a structured turnaround, expression, wardrobe, consistency, and output plan.

## Pi Mood Board Plan

Creates a role-aware mood-board manifest with categories and source references.

## Pi Storyboard Plan

Converts shot-list JSON into planned storyboard panels with stable scene and shot links.

## Pi Production Bible

Creates a draft story, series, character, world, location, continuity, visual, voice, music, sound, workflow, or production bible.

## Pi Production Build Plan

Creates a selective build plan for fresh, resume, incremental, repair, rebuild, validation, or dry-run compilation.

## Pi Fountain Screenplay

Creates a valid Fountain starter document from title, author, source text, and a default location.

## Pi Parse Fountain

Parses title fields, scenes, action, character cues, parentheticals, dialogue, transitions, sections, notes, and page breaks.

## Pi Screenplay Breakdown

Creates scene records with locations, time of day, characters, summaries, and production placeholders.

## Pi Shot List

Creates minimal, standard, or detailed starter coverage for every screenplay scene.

## Pi Production Plan

Creates a proportional stage plan and clearly states which stages are optional.

## Pi Compile Project / Pi Complete Production

Creates the complete project folder structure, starter documents, Fountain draft when appropriate, bibles, manifests, and NLE handoff documents.

The generated project has separate top-level folders for the story, screenplay, production bibles, mood boards, reference sheets, storyboards, scene and shot plans, prompts, ComfyUI workflows, generated media, editorial media, NLE files, tutorials, quality control, delivery, and archives. Every directory includes a plain-language `README.md`.

## Pi Create Skill

Creates an original Pi skill folder containing `SKILL.md` and `skill.json`.

## Pi Compile Tutorial

Compiles one or more workflows into a ComfyUI-native tutorial package.

## Pi Tutorial Load

Loads `tutorial.json` from a compiled tutorial directory.

## Pi Tutorial Preflight

Compares tutorial requirements with live registered node classes and model filenames.

## Pi Tutorial Stage Select

Selects a stage by one-based number.

## Pi Tutorial Stage Validate

Checks the analysis issues stored for a stage.

## Pi Tutorial Note

A normal ComfyUI node used as a canvas instruction card in annotated workflows.

## Pi Save Markdown

Writes Markdown atomically.

## Pi Export DOCX

Creates a readable DOCX with headings, paragraphs, lists, and code-style paragraphs using only Python's standard library.

## Pi Save JSON

Parses and writes formatted JSON.

## Pi Kdenlive Package

Creates a conservative Kdenlive/MLT project, portable timeline data, media map, profile, and assembly guides.

## Pi Show Text

Simple output node for viewing or forwarding text.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Quick start](quick-start.md) · [Next: Pi runtime and model-provider setup](pi-runtime.md)
<!-- DOC_NAV_FOOTER_END -->
