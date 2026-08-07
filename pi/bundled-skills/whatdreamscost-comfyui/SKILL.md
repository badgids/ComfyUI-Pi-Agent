# WhatDreamsCost-ComfyUI operating guide

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: voice-reference](../voice-reference/SKILL.md) · [Next skill: workflow-intelligence](../workflow-intelligence/SKILL.md)
<!-- DOC_NAV_END -->


Use this knowledge only when the user explicitly asks about WhatDreamsCost-ComfyUI/LTX Director or the current workflow contains one of its public node IDs. Do not inject this guide into unrelated Pi requests.

## Public node set

Recognize these nodes:

- `LTXDirector` — the main LTX Director 2 timeline editor.
- `LTXDirectorGuide` — Director guide helper.
- `LTXDirectorCropGuides` — crop-guide helper.
- `LTXKeyframer` — first/middle/last frame/keyframe workflow helper.
- `MultiImageLoader` — gallery-style multi-image loading/reordering and preprocessing.
- `LTXSequencer` — sequence/guide construction for LTX workflows.
- `SpeechLengthCalculator` — estimates video duration from quoted dialogue.
- `LoadAudioUI` — interactive audio loading/trimming.
- `LoadVideoUI` — interactive video loading/trimming/resizing/preview.

The pack is GPL-3.0. ComfyUI-Pi is also GPL-3.0, but still prefer interoperability and the upstream project's own current example workflows instead of copying or freezing a private snapshot of its large frontend implementation.

## What LTX Director does

LTX Director is a timeline-oriented front end for LTX video generation. Its current public feature set includes:

- Text-to-video and image-to-video.
- Multiple prompt segments and Prompt Relay.
- First, middle, and last-frame/keyframe guidance.
- Video segments and video extension.
- IC-LoRA reference images/video.
- Custom audio.
- Audio inpainting.
- Retake Mode.
- Timeline save/load.
- Model caching and performance paths.
- SageAttention/Triton-aware workflows where the installed dependencies support them.

Do not confuse this with MiniMax H3 Director. MiniMax H3 Director was derived from the LTX Director editing concept, but H3 uses different conditioning, different model paths, different prompt semantics, and a different latent/audio architecture.

## Frontend-managed state

`LTXDirector` exposes normal typed inputs/outputs, but several important fields are managed by the timeline frontend:

- `timeline_data`
- `local_prompts`
- `segment_lengths`
- `guide_strength`

Treat these as frontend-managed state. Do not guess indexes in `widgets_values` and do not rewrite serialized timeline state by hand unless a schema-aware edit path has validated the exact installed version.

When a user asks Pi to change shots, timing, guide frames, IC-LoRA media, custom audio, or retake state, prefer one of these approaches:

1. Tell the user what to change in the LTX Director timeline UI.
2. Use a validated frontend/API adapter if one exists for that installed version.
3. If generating a new workflow, start from the installed pack's own current example workflow and preserve its timeline serialization.

## Important LTX Director roles

The current Director schema includes roles such as:

- model
- clip
- optional audio VAE
- optional latent
- global prompt
- start/end/duration in seconds and frames
- timeline data
- custom audio toggle
- custom motion toggle
- audio inpainting toggle
- local prompts
- segment lengths
- Prompt Relay epsilon
- frame rate/display mode
- guide strengths
- width/height/resize/divisibility/compression
- override audio

Its outputs include patched model, positive conditioning, video latent, audio latent, guide data, motion guide data, frame rate, and combined audio.

Always validate these roles against live `/object_info` before editing a workflow because the upstream project can evolve.

## Prompt Relay

Prompt Relay is used to give timeline segments separate prompt influence. The current pack has a fast path for a single active prompt that bypasses attention masking. Do not force Prompt Relay when the timeline only needs one prompt.

For multi-prompt timelines:

- Preserve the global prompt as persistent scene/character context.
- Keep segment prompts aligned with their intended timeline lengths.
- Do not silently delete empty segments; use the upstream fallback behavior or ask the user.
- Treat `epsilon` as a Prompt Relay boundary/penalty control, not ordinary CFG.

## Frame and latent rules

When the Director auto-generates an LTXV latent, current upstream code follows the LTXV `8n+1` pixel-frame rule. Do not apply MiniMax H3's `17k+5` rule here.

Guide images can represent first, middle, or last-frame positions. `isEndFrame` state is meaningful. Preserve guide strength and frame placement when editing.

## Models and loaders

Current upstream release notes explicitly call out using `CLIPLoader` type `ltxv` in LTX workflows. Validate the live workflow and installed LTXVideo node schemas before changing it.

Do not invent model filenames. Inspect:

- live model inventories,
- workflow metadata,
- installed example workflows,
- live `/object_info`.

The upstream repository currently ships separate LTX Director example workflows for distilled/safetensors-style usage and GGUF usage. When GGUF is requested, use the installed GGUF example as the baseline instead of swapping a `.safetensors` filename for `.gguf` inside another loader.

## GGUF

For GGUF workflows:

- Verify ComfyUI-GGUF is installed and its loader classes are registered.
- Preserve the upstream GGUF workflow's loader topology.
- Validate LoRA/patch compatibility against the installed versions.
- Mixed GGUF/safetensors components are acceptable only when the live graph supports them.
- Never assume filename extension alone establishes architecture compatibility.

## IC-LoRA and references

LTX Director 2 supports IC-LoRA workflows for reference motion/style and reference images in current upstream releases.

When asked to use IC-LoRA:

- Verify the installed LTXVideo/KJNodes components expected by the selected workflow.
- Use the upstream example/current schema as the baseline.
- Keep reference media roles explicit.
- Do not convert an unrelated video track into IC-LoRA simply because a reference was supplied.

## Audio

The pack supports custom audio and audio inpainting. It can also combine timeline audio and expose `combined_audio`.

Do not conflate:

- generated audio,
- imported timeline audio,
- audio inpainting,
- audio taken from a reference/IC-LoRA video,
- final NLE soundtrack/stems.

When editing audio behavior, preserve the user's intent and validate the audio VAE/latent path used by the installed workflow.

## Retake Mode

Retake Mode is an LTX Director feature for regenerating a selected region of an existing video. Treat it as a specialized Director workflow, not as a generic text-to-video option. Preserve the base video, selection range, continuity anchors, and audio policy.

## Workflow creation policy

When asked to create a WhatDreamsCost workflow:

1. Detect whether the pack is installed.
2. Enumerate its installed example workflows.
3. Select the closest upstream example:
   - Director distilled for ordinary current Director workflows.
   - Director GGUF for GGUF.
   - custom-audio example for custom-audio FFLF.
   - 2-stage/3-stage FFLF examples when those modes are requested.
4. Copy the workflow as a new project artifact; never overwrite the upstream example.
5. Inspect live node schemas.
6. Modify only safe typed inputs/connections automatically.
7. Preserve frontend-managed timeline state unless a version-aware adapter can edit it safely.
8. Validate the resulting workflow.
9. Return the source workflow, changes, warnings, and missing dependencies.

If the pack is not installed, provide a plan/missing-dependency report. Do not fabricate an executable workflow containing node classes that are unavailable.

## Workflow repair policy

Check for:

- Missing WhatDreamsCost node classes.
- LTXVideo/KJNodes dependency mismatches.
- Wrong CLIP loader type.
- Missing or incompatible diffusion/text/audio components.
- Broken Prompt Relay connections.
- Missing guide data/motion guide data consumers.
- Missing media files.
- Stale frontend/timeline serialization.
- Incorrect safetensors/GGUF loader topology.

Automatic repair may fix ordinary graph links and model substitutions only when live schemas make the change unambiguous. Timeline serialization changes should be suggested rather than guessed.

## Related auxiliary nodes

`MultiImageLoader`, `LTXSequencer`, and `LTXKeyframer` are useful outside LTX Director. Do not require the main Director node merely because one of these nodes appears.

`LoadVideoUI` and `LoadAudioUI` are media utility nodes with interactive frontend behavior. Preserve trimming/resizing/file-selection state and inspect live schemas before generating API-only variants.

`SpeechLengthCalculator` is useful for deriving a target duration from dialogue. Treat its duration as planning input; still enforce the actual target model's frame/duration constraints later.

## Context discipline

This entire guide is optional context. It must be loaded only for a matching user request, matching workflow node ID, or explicit integration call. Unrelated Pi conversations should receive none of it.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: voice-reference](../voice-reference/SKILL.md) · [Next skill: workflow-intelligence](../workflow-intelligence/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
