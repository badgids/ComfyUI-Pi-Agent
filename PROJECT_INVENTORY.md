# Project inventory

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Release notes](RELEASE_NOTES.md)
<!-- DOC_NAV_END -->


## Release

- Version: 0.1.15
- Creator: Alan D. Guice (Badgids)
- License: GPL-3.0-only

## Contents

- ComfyUI nodes: 55
- Bundled Pi skills: 34
- Core documentation guides: 31
- Total linked Markdown documentation/procedure files: 76
- Test modules: 14
- Example workflows: 3
- First-class lazy node-pack integrations: 4
- Manifest-tracked source files: 168

## Context-efficiency guarantees

- Pi starts with context-file, extension, skill, prompt-template, theme, and Pi-session discovery disabled.
- Node-pack adapters are imported only when a message or workflow matches their registry entry.
- A deterministic host-side task router selects at most a few matching bundled procedures; weak local models do not need to choose from the complete skill library themselves.
- Every Pi turn receives a compact current-job envelope with an explicit completion rule; the stable core contract is injected only when a new hidden scope is established.
- Normal matched requests receive compact, task-targeted guidance; complete skill guides load only for explicit deep/tutorial requests.
- Sidebar and Pi Agent Prompt workflow context uses a bounded digest first; full workflow JSON is made available locally only for on-demand reading.
- Stateful sidebar chat resets Pi's hidden scope when integration/project/workflow context changes, then restores only a bounded clean visible transcript.
- Installed live ComfyUI schemas and the installed node pack's own example workflows outrank bundled static compatibility profiles.
- Pi built-in auto-compaction is disabled over RPC when supported; ComfyUI-Pi performs a bounded continuity handoff/reset at a configurable 80–95% threshold (82.5% default).
- Current Pi RPC `get_session_stats.contextUsage` is preferred for pressure measurement; assistant usage + model context window remains a compatibility fallback.
- Handoff generation uses a separate fresh Pi process and references large workflows/assets by path instead of embedding them.
- Pi built-in slash commands are bridged host-side before LLM routing; the slash-command catalog itself does not consume model context.
- Local-server discovery/configuration is explicit and on-demand; no llama.cpp/Ollama/LM Studio/vLLM endpoint is probed at plugin startup. llama.cpp router model IDs come from its live catalog; unloaded or sleeping models are explicitly woken and the routed model endpoint is verified ready before Pi RPC starts, using the user-configured chat timeout as the wait budget.

## First-class integrations

- ComfyUI-MiniMaxH3-Director (`seesee75-commits/ComfyUI-MiniMaxH3-Director`)
- WhatDreamsCost-ComfyUI (`WhatDreamsCost/WhatDreamsCost-ComfyUI`)
- ComfyUI-scene-camera-action (`arturitu/ComfyUI-scene-camera-action`)
- ComfyUI-MiniMax-H3-Turbo (`Larryvrh/ComfyUI-MiniMax-H3-Turbo`)

## Registered nodes

- `PiAgentPrompt`
- `PiAgentStatus`
- `PiAudioWorkflowPlan`
- `PiCharacterSheetPlan`
- `PiCompleteProduction`
- `PiDocxExport`
- `PiFountainParse`
- `PiFountainScreenplay`
- `PiImageWorkflowPlan`
- `PiIntegrationContextRouter`
- `PiJsonSave`
- `PiKdenlivePackage`
- `PiKrea2EditPlan`
- `PiMarkdownSave`
- `PiMiniMaxH3DirectorInspect`
- `PiMiniMaxH3DirectorPlan`
- `PiMiniMaxH3DirectorStatus`
- `PiMiniMaxH3DirectorWorkflow`
- `PiMiniMaxH3TurboInspect`
- `PiMiniMaxH3TurboPlan`
- `PiMiniMaxH3TurboStatus`
- `PiMiniMaxH3TurboWorkflow`
- `PiModelInventory`
- `PiModelProfiles`
- `PiModelResolver`
- `PiMoodBoardPlan`
- `PiProductionBible`
- `PiProductionBuildPlan`
- `PiProjectCompile`
- `PiProjectPlan`
- `PiPromptPackage`
- `PiQwenImageEditPlan`
- `PiReferenceAsset`
- `PiSceneCameraActionInspect`
- `PiSceneCameraActionPlan`
- `PiSceneCameraActionStatus`
- `PiSceneCameraActionWorkflow`
- `PiScreenplayBreakdown`
- `PiShotList`
- `PiShowText`
- `PiSkillCreate`
- `PiStoryboardPlan`
- `PiTutorialCompile`
- `PiTutorialLoad`
- `PiTutorialNote`
- `PiTutorialPreflight`
- `PiTutorialStageSelect`
- `PiTutorialStageValidate`
- `PiWhatDreamsCostInspect`
- `PiWhatDreamsCostPlan`
- `PiWhatDreamsCostStatus`
- `PiWhatDreamsCostWorkflow`
- `PiWorkflowAnalyze`
- `PiWorkflowRepair`
- `PiWorkflowValidate`

## Bundled Pi skills

- `ace-step-1-5`
- `audio-generation-router`
- `character-reference`
- `comfyui-tutorial-compile`
- `comfyui-tutorial-update`
- `complete-production`
- `document-export`
- `flux-2-klein-image`
- `fountain-screenplay`
- `gguf-model-resolution`
- `image-generation-router`
- `incremental-production-compiler`
- `kdenlive-handoff`
- `krea-2-edit`
- `krea-2-image`
- `minimax-h3-director`
- `minimax-h3-turbo`
- `moodboard`
- `music-audio-reference`
- `narrative-project`
- `qwen-image`
- `qwen-image-edit`
- `qwen3-tts`
- `reference-asset-system`
- `scene-camera-action`
- `screenplay-breakdown`
- `shot-planning`
- `stable-audio-3`
- `story-to-screenplay`
- `storyboard`
- `voice-reference`
- `whatdreamscost-comfyui`
- `workflow-intelligence`
- `z-image`

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/audio-music-voice.md`](docs/audio-music-voice.md)
- [`docs/compatibility.md`](docs/compatibility.md)
- [`docs/context-handoff.md`](docs/context-handoff.md)
- [`docs/development.md`](docs/development.md)
- [`docs/dynamic-integration-context.md`](docs/dynamic-integration-context.md)
- [`docs/image-generation-editing.md`](docs/image-generation-editing.md)
- [`docs/index.md`](docs/index.md)
- [`docs/installation.md`](docs/installation.md)
- [`docs/kdenlive-nle.md`](docs/kdenlive-nle.md)
- [`docs/local-llm-slash-commands.md`](docs/local-llm-slash-commands.md)
- [`docs/limitations.md`](docs/limitations.md)
- [`docs/minimax-h3-director.md`](docs/minimax-h3-director.md)
- [`docs/minimax-h3-turbo.md`](docs/minimax-h3-turbo.md)
- [`docs/model-formats-gguf.md`](docs/model-formats-gguf.md)
- [`docs/node-reference.md`](docs/node-reference.md)
- [`docs/pi-runtime.md`](docs/pi-runtime.md)
- [`docs/production-compiler.md`](docs/production-compiler.md)
- [`docs/project-directory-layout.md`](docs/project-directory-layout.md)
- [`docs/quick-start.md`](docs/quick-start.md)
- [`docs/references-bibles.md`](docs/references-bibles.md)
- [`docs/roadmap.md`](docs/roadmap.md)
- [`docs/scene-camera-action.md`](docs/scene-camera-action.md)
- [`docs/security.md`](docs/security.md)
- [`docs/sidebar-chat.md`](docs/sidebar-chat.md)
- [`docs/small-model-reliability.md`](docs/small-model-reliability.md)
- [`docs/troubleshooting.md`](docs/troubleshooting.md)
- [`docs/tutorials.md`](docs/tutorials.md)
- [`docs/whatdreamscost-comfyui.md`](docs/whatdreamscost-comfyui.md)
- [`docs/workflow-intelligence.md`](docs/workflow-intelligence.md)
- [`docs/writing-screenplay.md`](docs/writing-screenplay.md)

## Tests

- `test_agent_guidance.py`
- `test_chat.py`
- `test_context_handoff.py`
- `test_documentation_navigation.py`
- `test_documents_projects.py`
- `test_fountain.py`
- `test_integrations.py`
- `test_license_and_release.py`
- `test_media_plans.py`
- `test_nodes.py`
- `test_package_entrypoint.py`
- `test_slash_commands_local_llm.py`
- `test_tutorial_nle.py`
- `test_workflow.py`

## Example workflows

- `examples/workflows/01_status_and_models.json`
- `examples/workflows/02_project_plan.json`
- `examples/workflows/03_tutorial_controller_builder.json`

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Release notes](RELEASE_NOTES.md)
<!-- DOC_NAV_FOOTER_END -->
