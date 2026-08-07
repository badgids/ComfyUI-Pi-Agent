# ComfyUI Pi Agent Production Suite

A ComfyUI custom-node package that connects **Pi Agent** reasoning with practical workflow analysis, model discovery, project planning, screenplay tools, reference manifests, tutorial compilation, document export, and Kdenlive-first editorial handoff.

**Creator:** Alan D. Guice (**Badgids**)  
**License:** GPL-3.0  
**Release:** 0.1.11

> This project is designed to be powerful without being confusing. The documentation uses plain language, short steps, and concrete examples. Technical details are kept intact instead of being hidden or oversimplified.

---

## What this custom node is for

ComfyUI can generate images, video, speech, music, sound, and many other kinds of media. Large projects become difficult when they need many workflows, references, prompts, scripts, shot lists, and output files.

ComfyUI Pi Agent helps organize that work. It can:

- inspect and explain ComfyUI workflows;
- validate and safely repair basic workflow structure;
- discover installed model files without inventing filenames;
- understand safetensors and GGUF as component formats;
- build model-aware prompt packages;
- create reference-asset manifests for characters, voices, audio, mood boards, and storyboards;
- create and parse Fountain screenplays;
- create screenplay breakdowns and starter shot lists;
- create complete project directory structures and documentation;
- compile one or more workflows into a thorough **ComfyUI-native tutorial**;
- export Markdown, DOCX, Fountain, and JSON files;
- prepare a Kdenlive-first editorial package with a portable timeline fallback;
- call Pi through its JSONL RPC mode when Pi is installed and configured;
- chat with Pi directly from a standard ComfyUI left-sidebar chat interface without adding a node;
- recognize, explain, inspect, plan, create, and safely edit workflows for **ComfyUI-MiniMaxH3-Director** when that pack is installed;
- recognize, explain, inspect, plan, create, and safely edit workflows for **WhatDreamsCost-ComfyUI**, including LTX Director, Prompt Relay, keyframes, IC-LoRA, audio, and its utility nodes;
- understand and operate **ComfyUI-scene-camera-action**, including SceneState staging presets, human/car acting, camera directing, and captured previz reference output;
- understand and operate **ComfyUI-MiniMax-H3-Turbo**, including its Turbo LoRA, dual-schedule 4-step sampler, strength tuning, low-VRAM mode, T2V/I2V use, and H3 joint audio/video constraints;
- dynamically load node-pack knowledge only when the current request or workflow needs it, instead of filling Pi's context window at startup;
- deterministically select a small set of task procedures so even weak local models are told how to stay on task, inspect before guessing, act, validate, and report evidence;
- preemptively create a compact continuity handoff around 82.5% context usage, reset Pi before built-in compaction, and automatically ingest the handoff so long work can continue.

Every major tool is available as a normal ComfyUI node. The optional sidebar is disabled by default and is not required.

---

## Important first-release boundary

Version 0.1.11 provides the working foundation, project compilers, tutorial compiler, document tools, workflow intelligence, Pi RPC connection, manifests, profiles, examples, and tests.

It does **not** bundle large AI model weights, third-party custom-node packs, Pi itself, Node.js, FFmpeg, or Kdenlive. It detects those tools when they are installed. Missing optional tools do not stop ComfyUI from starting.

The plugin never downloads anything during import.

---

# Table of contents

> **Documentation starts here:** [Documentation home and navigation map](docs/index.md). Every guide contains links to go **up**, **back**, **forward**, and to closely related guides.

> **Navigation guarantee:** the automated test suite verifies that every Markdown documentation/procedure file is reachable from this README through local links and that those local documentation links resolve.

## Start here

1. [Documentation home](docs/index.md)
2. [Installation](docs/installation.md)
3. [Quick start](docs/quick-start.md)
4. [Node reference](docs/node-reference.md)
5. [Troubleshooting](docs/troubleshooting.md)

## Agent, runtime, workflow, and model guides

6. [Pi runtime and model-provider setup](docs/pi-runtime.md)
7. [Small local model reliability](docs/small-model-reliability.md)
8. [Pi Agent sidebar chat](docs/sidebar-chat.md)
9. [Local LLM servers and Pi slash commands](docs/local-llm-slash-commands.md)
10. [Workflow intelligence](docs/workflow-intelligence.md)
11. [Model discovery, safetensors, and GGUF](docs/model-formats-gguf.md)
12. [Dynamic integration context](docs/dynamic-integration-context.md)
13. [Preemptive context handoff](docs/context-handoff.md)

## Media and production guides

14. [Image generation and editing profiles](docs/image-generation-editing.md)
15. [Music, speech, and audio profiles](docs/audio-music-voice.md)
16. [Project directory layout and asset organization](docs/project-directory-layout.md)
17. [References, mood boards, storyboards, and bibles](docs/references-bibles.md)
18. [Stories, books, Fountain, and screenplays](docs/writing-screenplay.md)
19. [Complete and incremental production compiler](docs/production-compiler.md)
20. [ComfyUI-native tutorial compiler](docs/tutorials.md)
21. [Kdenlive and NLE handoff](docs/kdenlive-nle.md)

## First-class node-pack integrations

22. [MiniMax H3 Director](docs/minimax-h3-director.md)
23. [WhatDreamsCost-ComfyUI](docs/whatdreamscost-comfyui.md)
24. [Scene Camera Action](docs/scene-camera-action.md)
25. [MiniMax H3 Turbo](docs/minimax-h3-turbo.md)

## Technical documentation

26. [Architecture](docs/architecture.md)
27. [Compatibility](docs/compatibility.md)
28. [Known limitations](docs/limitations.md)
29. [Security and path policy](docs/security.md)
30. [Development and testing](docs/development.md)
31. [Roadmap](docs/roadmap.md)

## Examples, skills, project records, and governance

32. [Example workflows](examples/workflows/README.md)
33. [Bundled Pi skills and procedures](pi/bundled-skills/README.md)
34. [Project inventory](PROJECT_INVENTORY.md)
35. [Release notes](RELEASE_NOTES.md)
36. [Changelog](CHANGELOG.md)
37. [Contributing](CONTRIBUTING.md)
38. [Agent and development rules](AGENTS.md)
39. [Security policy](SECURITY.md)
40. [Code of conduct](CODE_OF_CONDUCT.md)
41. [Third-party notices](THIRD_PARTY_NOTICES.md)
42. [GPL-3.0 license](LICENSE)
43. [Model-family profiles](data/model_profiles.json)

---

# Installation

## Method 1: Git clone

Open a terminal in the `custom_nodes` directory inside your ComfyUI installation.

### Linux, macOS, or WSL

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/Badgids/ComfyUI-Pi-Agent.git
```

### Windows PowerShell

```powershell
cd C:\path\to\ComfyUI\custom_nodes
git clone https://github.com/Badgids/ComfyUI-Pi-Agent.git
```

Restart ComfyUI.

There are no required Python packages beyond the standard library, so there is no mandatory `pip install` command for the first release.

## Method 2: ZIP

1. Download the project ZIP.
2. Extract it into `ComfyUI/custom_nodes`.
3. Make sure the directory contains this `README.md` and the top-level `__init__.py`.
4. Restart ComfyUI.

## Confirm that it loaded

In ComfyUI:

1. Double-click an empty part of the canvas.
2. Search for `Pi Agent Status`.
3. Add the node.
4. Queue it.

The node reports the plugin version and whether the Pi executable was found.

Read the full [installation guide](docs/installation.md) when ComfyUI uses a portable Python build, Docker, WSL, or a nonstandard user directory.

---

# Five-minute quick start

## 1. Check the plugin

Add and run:

```text
Pi Agent Status
```

Pi is optional for the non-agent project tools. A missing Pi executable is reported as a normal status message, not a startup error.

## 2. Inspect installed models

Add and run:

```text
Pi Model Inventory
```

The node asks ComfyUI for model filenames registered in categories such as checkpoints, diffusion models, text encoders, VAEs, LoRAs, ControlNets, and audio encoders.

## 3. Analyze a workflow

1. Save or copy a ComfyUI workflow JSON.
2. Paste the JSON or enter its path in `Pi Analyze Workflow`.
3. Run the node.

The result includes:

- workflow format;
- node count;
- link count;
- detected node types;
- detected input files;
- detected model-like filenames;
- missing live node classes;
- structural warnings and errors.

## 4. Create a project

Add `Pi Compile Project` and enter a simple request, for example:

```text
Create a three-minute animated short about a young pony who learns to cross a flooded creek.
```

The node creates a complete, organized project directory with writing, bibles, references, production, generated-media, editorial, quality-control, NLE, and delivery folders.

It labels the project **planned**, not complete. Media is only complete after the required workflows actually run and pass validation.

## 5. Compile a tutorial

Add `Pi Compile Tutorial`.

Supply one workflow object, a list of workflow objects, or a list of workflow paths as JSON:

```json
[
  "/path/to/01_character_sheet.json",
  "/path/to/02_storyboard.json",
  "/path/to/03_video.json"
]
```

The compiler creates:

- preserved original workflows;
- annotated tutorial workflows;
- stage-by-stage Markdown and DOCX guides;
- model and custom-node manifests;
- a Tutorial Controller workflow;
- a Project Overview workflow;
- validation and troubleshooting files.

The tutorial is completed entirely inside ComfyUI. No separate private WebUI is created.

---

# Node groups

## Runtime

- **Pi Agent Status** — finds Pi safely and reports plugin/runtime status.
- **Pi Agent Prompt** — sends a prompt to Pi through strict JSONL RPC mode; an optional workflow input enables lazy workflow-aware/node-pack-aware reasoning without dumping the full graph into context.

## Workflow intelligence

- **Pi Analyze Workflow**
- **Pi Validate Workflow**
- **Pi Repair Workflow**

## Models and prompts

- **Pi Model Inventory**
- **Pi Model Resolver**
- **Pi Model Profiles**
- **Pi Prompt Package**

## Image and audio planning

- **Pi Image Workflow Plan**
- **Pi Qwen Image Edit Plan**
- **Pi Krea 2 Edit Plan**
- **Pi Audio Workflow Plan**

## Video / MiniMax H3 Director

- **Pi MiniMax H3 Director Status** — detects the separately installed Director pack and its public nodes.
- **Pi MiniMax H3 Director Plan** — chooses FL2VA/ref2VA and validates duration/reference limits.
- **Pi MiniMax H3 Director Workflow** — creates a workflow from the installed Director pack's own current example workflow instead of fabricating a third-party graph.
- **Pi Inspect MiniMax H3 Director Workflow** — checks Director-specific model, VAE, prompt, reference, and timeline requirements.

## Video / Scene Camera Action

- **Pi Scene Camera Action Status** — detects `SceneNode`, `ActingNode`, and `DirectingNode`, installed presets, and the upstream staging skill.
- **Pi Scene Camera Action Plan** — plans staging, human/car acting, duration, and optional directing.
- **Pi Scene Camera Action Workflow** — creates a safe base Scene → Acting → Directing previz chain without inventing recorded frontend state.
- **Pi Inspect Scene Camera Action Workflow** — checks the chain, SceneState structure, actor settings, and frontend-managed editing boundaries.

## Video / MiniMax H3 Turbo

- **Pi MiniMax H3 Turbo Status** — detects the Turbo LoRA/sampler pack and its installed example workflow.
- **Pi MiniMax H3 Turbo Plan** — plans T2V/I2V/FLF, steps, LoRA strength, and low-VRAM mode.
- **Pi MiniMax H3 Turbo Workflow** — creates from the installed upstream Turbo example and can attach first/last image inputs by named sockets.
- **Pi Inspect MiniMax H3 Turbo Workflow** — checks the Turbo LoRA, dual-schedule sampler, scheduler, H3 model path, and AV requirements.

## References and production memory

- **Pi Reference Asset**
- **Pi Character Sheet Plan**
- **Pi Mood Board Plan**
- **Pi Storyboard Plan**
- **Pi Production Bible**

## Writing and production planning

- **Pi Fountain Screenplay**
- **Pi Parse Fountain**
- **Pi Screenplay Breakdown**
- **Pi Shot List**
- **Pi Production Plan**
- **Pi Production Build Plan**
- **Pi Compile Project**
- **Pi Complete Production**

## Tutorials

- **Pi Compile Tutorial**
- **Pi Tutorial Load**
- **Pi Tutorial Preflight**
- **Pi Tutorial Stage Select**
- **Pi Tutorial Stage Validate**
- **Pi Tutorial Note**

## Documents and NLE

- **Pi Save Markdown**
- **Pi Export DOCX**
- **Pi Save JSON**
- **Pi Kdenlive Package**
- **Pi Show Text**

The complete input and output reference is in [docs/node-reference.md](docs/node-reference.md).

---

# Pi Agent connection

The custom node discovers Pi in this order:

1. the explicit executable path entered in the node;
2. the `PI_AGENT_EXECUTABLE` environment variable;
3. the system `PATH`.

Pi is started with `--mode rpc`. The Python client sends one JSON object per line and reads Pi events until the agent is fully settled.

Pi still needs a model provider. In the optional sidebar, **Provider** then **Model** are directly beneath the chat box. The Provider dropdown covers Pi's current built-in provider catalog plus local/custom providers; hosted models come from Pi's live available-model catalog, while local hosts populate their own reported models on selection. Common local endpoints are automatic and endpoint editing is advanced/optional. Provider credentials and models are managed by Pi, not written into ComfyUI workflows.

Read [docs/pi-runtime.md](docs/pi-runtime.md) and [docs/local-llm-slash-commands.md](docs/local-llm-slash-commands.md).

---

# Model formats and GGUF

The plugin does not assume that a model is just one file. A usable model may require:

- diffusion or transformer weights;
- one or more text encoders;
- a vision encoder;
- a multimodal projector;
- a VAE or audio codec;
- a required edit LoRA;
- matching loader nodes;
- a variant-specific sampling profile.

`Pi Model Resolver` searches the filenames ComfyUI already knows. It can prefer safetensors or GGUF, but it does not pretend that two similar names are compatible.

The bundled profile registry includes:

- Qwen Image;
- Qwen Image Edit;
- Krea 2;
- Krea 2 Edit;
- FLUX.2 Klein;
- Z-Image;
- ACE-Step 1.5 and XL;
- Qwen3-TTS;
- Stable Audio 3;
- MiniMax H3 Director (FL2VA/ref2VA interoperability profile);
- WhatDreamsCost LTX Director (distilled/GGUF workflow interoperability profile).
- Scene Camera Action 3D previz/SceneState interoperability profile;
- MiniMax H3 Turbo 4-step LoRA/sampler interoperability profile.

These profiles describe capability and component expectations. Live ComfyUI node schemas and installed templates remain the authority for actual workflow construction.

Read [docs/model-formats-gguf.md](docs/model-formats-gguf.md).

---

# MiniMax H3 Director integration

ComfyUI-Pi includes first-class interoperability knowledge for the separately installed **ComfyUI-MiniMaxH3-Director** node pack. It recognizes the Director, Preview Override, Retake Stitch, and Enhance Prompt nodes; understands FL2VA versus ref2VA; knows the model/VAE roles, reference limits, prompt formats, frame-grid rules, joint audio/video decode, retake behavior, and safe editing boundaries.

The integration does **not** copy the upstream GPL-3.0 Python/JavaScript code into this GPL-3.0 repository. When asked to create a Director workflow, ComfyUI-Pi locates the user's installed Director pack and starts from that pack's own current example workflow. If the pack is missing, Pi reports the missing dependency instead of inventing a fake workflow.

The knowledge is **not** injected at Pi startup. The dynamic integration router loads the MiniMax H3 Director guide only when the user asks about it, when a matching node ID appears in the attached workflow, or when the user explicitly calls its integration node.

Read [docs/minimax-h3-director.md](docs/minimax-h3-director.md) and [docs/dynamic-integration-context.md](docs/dynamic-integration-context.md).

# WhatDreamsCost-ComfyUI integration

ComfyUI-Pi also includes first-class knowledge for **WhatDreamsCost-ComfyUI**. It recognizes `LTXDirector`, `LTXDirectorGuide`, `LTXDirectorCropGuides`, `LTXKeyframer`, `MultiImageLoader`, `LTXSequencer`, `SpeechLengthCalculator`, `LoadAudioUI`, and `LoadVideoUI`. It understands the LTX Director timeline, Prompt Relay, first/middle/last guide frames, custom audio, audio inpainting, IC-LoRA reference workflows, Retake Mode, timeline save/load, and the upstream distilled and GGUF example-workflow paths.

When asked to create a WhatDreamsCost workflow, ComfyUI-Pi prefers the **installed pack's own current example workflow** and then uses live ComfyUI schemas for safe changes. It does not guess the large timeline frontend's private `widgets_values` indexes or blindly rewrite `timeline_data`.

This integration is also lazy: unrelated Pi conversations receive none of the WhatDreamsCost guide.

Read [docs/whatdreamscost-comfyui.md](docs/whatdreamscost-comfyui.md).

# Scene Camera Action integration

ComfyUI-Pi recognizes `SceneNode`, `ActingNode`, and `DirectingNode` from **ComfyUI-scene-camera-action**. It understands the upstream SceneState/blockout contract, actor-aware spawn/layout rules, human/car acting stage, camera-cut directing stage, and the captured video/stage outputs used as previz references.

The integration deliberately does not manufacture recorded `motion_data` or `directing_data`: those are interactive frontend states owned by the upstream widgets. Pi can create and edit SceneState JSON, build the public three-node chain, inspect/repair the graph, and explain how to use the output in downstream generation.

Read [docs/scene-camera-action.md](docs/scene-camera-action.md).

# MiniMax H3 Turbo integration

ComfyUI-Pi recognizes `MiniMaxH3TurboLoRA` and `MiniMaxH3TurboSampler` from **ComfyUI-MiniMax-H3-Turbo**. It understands the required MODEL insertion, the custom dual video/audio schedule, `simple`/4-step starting profile, LoRA strength tuning, `low_vram` sharpness/VRAM trade-off, pruned/full H3 base support, and H3's 24 fps / 17k+5 constraints.

A Turbo request does not automatically load the separate MiniMax H3 Director guide. The two integrations are loaded together only when the user asks to combine them or the workflow actually contains both node packs.

Read [docs/minimax-h3-turbo.md](docs/minimax-h3-turbo.md).

# Small local model reliability

ComfyUI-Pi does not assume that the connected local LLM is large or highly capable. The host code keeps a short operating contract, classifies the current job deterministically, selects only a few matching bundled procedures, supplies a concrete completion rule, and resets stale hidden procedure context when the work changes.

This means a small model does not have to remember the whole plugin, choose from every skill, or infer basic rules such as "inspect the workflow before changing it". Large workflows, manuals, and project files remain available by path and are read only when the task needs their exact contents.

The design cannot make a very weak model reason like a much stronger model, but it removes avoidable ambiguity and moves routing, context control, and safety rules into deterministic code.

Read [docs/small-model-reliability.md](docs/small-model-reliability.md).

# Dynamic integration context

ComfyUI-Pi keeps Pi's starting context deliberately lean. Its supervised RPC subprocess disables Pi's automatic project context files, discovered extensions, discovered skills, prompt templates, themes, project trust, and Pi-side session persistence for that run. The tiny integration registry stays host-side and is not injected into the model at startup.

For each request, the router checks the user's message and any attached/current workflow. Only a matching node pack is loaded. Normal matched requests receive a compact, task-targeted integration summary; the full bundled guide is reserved for explicit comprehensive-guide/tutorial/deep-dive requests. Unrelated requests receive **zero** MiniMax H3 Director, WhatDreamsCost, Scene Camera Action, or MiniMax H3 Turbo knowledge. In sidebar chat, large active workflows are represented by a compact digest plus an on-demand local workflow file instead of pasting the entire graph into every turn.

ComfyUI-Pi also prevents previously injected pack knowledge from lingering indefinitely in stateful chat. When the relevant integration/project/workflow scope changes, it resets Pi's in-memory RPC session and rehydrates only a bounded clean user-visible transcript before injecting the new scope.

This keeps ordinary chat, writing, project planning, and unrelated ComfyUI work from paying the context-window cost of every supported node pack. See [docs/dynamic-integration-context.md](docs/dynamic-integration-context.md) and [docs/pi-runtime.md](docs/pi-runtime.md).

---

# ComfyUI-native tutorial compiler

The tutorial compiler is intentionally native to ComfyUI.

It does **not** include:

- a private WebUI;
- a standalone tutorial website;
- a second server;
- an external launcher.

It creates normal ComfyUI workflows containing tutorial notes and groups. The generated Tutorial Controller workflow loads the tutorial manifest, performs preflight checks, selects stages, and validates progress.

A complete tutorial package may contain:

```text
README.md
QUICK_START.md
QUICK_START.docx
COMPLETE_TUTORIAL.md
COMPLETE_TUTORIAL.docx
TROUBLESHOOTING.md
TROUBLESHOOTING.docx
tutorial.json
Tutorial_Controller.json
Project_Overview.json
original workflows
annotated workflows
stage guides
model manifests
custom-node manifests
validation reports
```

Read [docs/tutorials.md](docs/tutorials.md).

---

# Project and production compiler

`Pi Compile Project` accepts a simple request and creates a complete project structure. It is safe to use independently or as the beginning of a larger pipeline.

The compiler creates only starter documents and manifests. It does not falsely claim that ungenerated media exists.

Every generated project begins with `START_HERE.md` and a complete directory guide. Major creative assets have their own plainly labeled top-level directory:

```text
00_PROJECT_ADMIN
01_STORY
02_SCREENPLAY
03_PRODUCTION_BIBLES
04_MOOD_BOARDS
05_REFERENCE_SHEETS
06_STORYBOARDS
07_SCENE_AND_SHOT_PLANS
08_PROMPTS
09_COMFYUI_WORKFLOWS
10_GENERATED_MEDIA
11_EDITORIAL_MEDIA
12_NLE_PROJECT
13_TUTORIALS_AND_DOCUMENTATION
14_QUALITY_CONTROL
15_DELIVERY
16_ARCHIVE
```

Every generated directory and subdirectory contains a `README.md` explaining exactly what belongs there. The compiler also creates `asset-catalog.json` and `directory-map.json`, so users and automation can locate assets without guessing.

The first release supports:

- project brief and assumptions;
- Markdown and DOCX documents;
- starter Fountain screenplay for narrative requests;
- empty structured bibles;
- production and asset manifests;
- Kdenlive assembly-document placeholders;
- clear planned/partial/complete status boundaries.

Read [the project directory layout guide](docs/project-directory-layout.md) and [the production compiler guide](docs/production-compiler.md).

---

# Kdenlive handoff

Kdenlive is the default NLE target.

`Pi Kdenlive Package` accepts a production manifest and creates:

- a basic Kdenlive/MLT project;
- an OTIO-style JSON fallback;
- a timeline JSON file;
- a media map;
- a project profile;
- a Markdown assembly guide;
- a DOCX assembly guide.

The native Kdenlive writer is intentionally conservative. Complex effects, title templates, nested sequences, transitions, and version-specific features should be finished inside Kdenlive. The portable manifest and assembly guide remain available when a native project needs repair.

Read [docs/kdenlive-nle.md](docs/kdenlive-nle.md).

---

# Optional ComfyUI sidebar chat

The sidebar accepts Pi's documented built-in slash-command names through a host-side RPC bridge. Provider/model switching is intentionally simple: directly beneath the chat box choose **Provider** first, then **Model**. Pi built-in providers use Pi's live available-model catalog; local hosts such as **llama.cpp**, **Ollama**, **LM Studio**, and **vLLM** populate the models their own server reports. Common local endpoints are automatic; open the advanced local-host settings only when your server uses a different address. Type `/` in the composer for the command picker. See [Local LLM servers and Pi slash commands](docs/local-llm-slash-commands.md).

The optional sidebar is disabled by default. Enable it in ComfyUI settings:

```text
Pi Agent: Show optional sidebar after restart
```

Reload or restart the ComfyUI frontend after changing it.

The **Pi Agent** sidebar now opens as a standard AI chat interface. You can talk to and instruct Pi directly without placing a Pi node on the canvas. It includes persistent chat sessions, normal selectable message text, per-message **Copy** buttons, **Copy chat**, a multiline paste-friendly composer, Enter-to-send, Shift+Enter for a new line, a Stop button, and optional current-workflow/project context.

Normal text selection is intentionally enabled throughout the conversation, so you can drag-select any portion of a response and use Ctrl/Cmd+C and Ctrl/Cmd+V as expected.

The chat also auto-recognizes MiniMax H3 Director workflows. For example:

```text
Explain this MiniMax H3 Director workflow.
Create an H3 Director workflow for a 7-second shot with two character references.
Check whether this Director timeline exceeds the ref2VA limits.
```

The sidebar remains optional. Every major plugin capability is still available through ComfyUI nodes, and this is not a separate WebUI.

Read [docs/sidebar-chat.md](docs/sidebar-chat.md).

---

# Safety and privacy

This package follows these rules:

- No personal path is hardcoded.
- No model or dependency is downloaded during import.
- No API key is stored in a workflow by the plugin.
- Original workflows are preserved before repair or tutorial annotation.
- File writes use atomic replacement.
- Relative project paths are preferred.
- Missing models and nodes are reported instead of invented.
- Pi is launched with an argument array, never a shell command string.
- Optional failures do not stop ComfyUI from loading.

Read [docs/security.md](docs/security.md) and [SECURITY.md](SECURITY.md).

---

# Testing

The repository uses Python's built-in `unittest`, so tests need no extra test framework.

From the project directory:

```bash
python -m unittest discover -s tests -v
```

The tests run without ComfyUI by using compatibility fallbacks.

Read [docs/development.md](docs/development.md).

---

# Updating

From the cloned repository:

```bash
git pull
```

Restart ComfyUI after updating Python or JavaScript files.

Review [CHANGELOG.md](CHANGELOG.md) before updating a production environment.

---

# Credits

Created by **Alan D. Guice (Badgids)**.

This project builds on the public extension systems and documentation of ComfyUI and Pi Agent. ComfyUI-Pi includes interoperability knowledge for separately distributed node packs including GPL-3.0 **ComfyUI-MiniMaxH3-Director** by `seesee75-commits`, GPL-3.0 **WhatDreamsCost-ComfyUI** by `WhatDreamsCost`, MIT **ComfyUI-scene-camera-action** by `arturitu` (whose upstream staging skill is Apache-2.0), and Apache-2.0 **ComfyUI-MiniMax-H3-Turbo** by `Larryvrh`. Their source code and weights are not bundled into ComfyUI-Pi. Third-party models, custom nodes, media, fonts, and model weights keep their own licenses. The GPL-3.0 license covers the original ComfyUI-Pi code and documentation in this repository. Third-party projects and assets keep their own copyrights and license notices. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

# License

GNU General Public License v3.0. See [LICENSE](LICENSE).
