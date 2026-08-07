# MiniMax H3 Director

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: krea-2-image](../krea-2-image/SKILL.md) · [Next skill: minimax-h3-turbo](../minimax-h3-turbo/SKILL.md)
<!-- DOC_NAV_END -->


Use this skill whenever a request or workflow involves **ComfyUI-MiniMaxH3-Director**, MiniMax H3 video generation, `MiniMaxH3DirectorCS`, FL2VA/ref2VA, Director retakes, Director prompt enhancement, or Director live preview.

## Purpose

ComfyUI-Pi must be able to recognize, explain, create from the installed pack's examples, edit safely, validate, repair, and incorporate MiniMax H3 Director workflows into larger productions.

The third-party node pack is GPL-3.0. This skill and ComfyUI-Pi's integration code are original GPL-3.0-licensed interoperability material. Never copy or bundle the third-party source or frontend JavaScript into ComfyUI-Pi.

## Detect first

1. Inspect the live node registry for:
   - `MiniMaxH3DirectorCS`
   - `MiniMaxH3PreviewOverrideCS`
   - `MiniMaxH3RetakeStitchCS`
   - `MiniMaxH3EnhancePromptCS`
2. If installed, prefer the pack's own `example_workflows/*.json` as the workflow creation baseline.
3. Inspect the current workflow and live node schemas before editing connections or model choices.
4. If the pack is not installed, return a precise missing-requirement report. Do not invent a runnable third-party graph.

## Conditioning paths

### Refs OFF — FL2VA

Use `minimax_h3_fl2va_*` weights for:
- text-to-video;
- first-frame anchoring;
- last-frame anchoring;
- first+last-frame video.

Images in the middle of the timeline are not FL2VA keyframes. Reference video/audio and image-reference conditioning require ref2VA.

### Refs ON — ref2VA

Use `minimax_h3_ref2va_*` weights for:
- character slots;
- reference images;
- reference videos;
- reference audio.

Do not swap FL2VA and ref2VA checkpoints just because the filenames are similar.

## Required core roles

- `UNETLoader` for FL2VA and/or ref2VA.
- `CLIPLoader` with **type `minimax`** for the Qwen3-VL MiniMax text encoder.
- MiniMax H3 video VAE.
- MiniMax H3 audio VAE when audio references or audio decode are required.
- `MiniMaxH3DirectorCS`.
- `BasicGuider` with no CFG.
- `SamplerCustomAdvanced` path; the pack's example starts with `res_multistep`, `simple`, about 20 steps.
- `VAEDecode` for video and `VAEDecodeAudio` for audio.
- `CreateVideo` and a video save node.

`MiniMaxH3PreviewOverrideCS` is optional but useful between Director.model and the sampler. `MiniMaxH3EnhancePromptCS` is optional for local-VLM prompt drafting. `MiniMaxH3RetakeStitchCS` is used after Retake Mode.

## Hard model rules

- Output: 24 fps.
- Frame count: align to the `17k+5` grid.
- Trained generation range: approximately 4-15 seconds per render.
- Native canvas policy: 768 px short edge, capped around 768x1344; keep dimensions divisible by 32.
- Reference images: at most 9.
- Reference video: at most 3 clips, 2-15 s each, no more than 15 s total.
- Reference audio: at most 3 clips.
- All reference files combined: at most 12.

The current public pack intentionally does **not** register its Director Chain node. For projects longer than 15 seconds, generate separate shots and assemble them in the NLE.

## Timeline and prompt semantics

The Director compiles timeline segments into MiniMax H3 storyboard text. Do not replace this with an LTX-style per-segment attention mask.

For the default MiniMax prompt format:
- `[Shot 1]` has no timestamp.
- Every later shot uses a strictly increasing `At MM:SS.mmm,` timestamp.
- Reusable characters can be represented by `<Subject N>` definitions tied to concrete `<Picture N>` inputs.
- Reference video uses `<Video N>`.
- Reference audio uses `<Audio N>`.
- `overall_soundscape` and `non_diegetic_music` are separate sections when non-empty.

The alternate ComfyUI prompt format uses H3 timeline notation such as `[0s-1.5s]`.

## Character slots

`@char1`, `@char2`, and `@char3` are Director character slots. In ref2VA they resolve to reference subjects/pictures. In FL2VA they can fall back to their analyzed text descriptions because the image references are not sent through the ref2VA path.

## Enhance Prompt

The Enhance Prompt node sends up to nine reference images plus an idea to a local vision endpoint and returns prompt text plus the same images. Its **global** preset should produce only the global description. It must not invent Director section labels, shot numbering, or `<Picture N>`/`<Subject N>` labels because the Director assigns those.

The **storyboard** preset can write shots/timestamps, but only use it when the Director timeline itself is not also carrying shot prompts; otherwise two independent shot numberings can collide.

## Retake

Retake Mode regenerates only a marked region of a base video. The Director uses the frame before and after the marked region as FL2VA anchors. After generation, `MiniMaxH3RetakeStitchCS` combines base head + retake + base tail and can preserve the base audio.

## Editing policy

When editing an existing Director workflow:

1. Preserve the original workflow.
2. Inspect live schemas and the installed pack version.
3. Inspect the Director's current `reference_mode`, prompt format, timeline media, and retake state.
4. Make loader/model substitutions only when component roles are known.
5. Prefer editing the timeline through the Director's frontend/state mechanisms.
6. **Never guess `widgets_values` indexes or hand-rewrite `timeline_data` from assumptions.**
7. Validate FL2VA/ref2VA checkpoint compatibility after any mode change.
8. Validate reference counts and durations.
9. Validate video/audio VAE branches.
10. Return a diff and warnings for any automated edit.

## Workflow creation policy

When asked to create a Director workflow:

1. Detect the installed Director pack.
2. Load its own current example workflow as the baseline.
3. Choose FL2VA or ref2VA from the user's required references.
4. Resolve the exact installed model filenames instead of inventing them.
5. Use live schemas for any additions or substitutions.
6. Keep Director timeline editing in the Director node itself.
7. Validate the completed graph before execution.

## Troubleshooting priorities

- Nodes missing: check ComfyUI >= 0.30.0, restart ComfyUI, hard-reload the browser.
- Timeline looks like plain widgets: stale frontend cache is likely; hard reload.
- CLIP input errors or nonsense output: check `CLIPLoader` type is `minimax`.
- Video decode fails/noise while audio works: verify the video VAE and audio VAE are on the correct decode branches.
- References ignored: check Refs ON/ref2VA plus the matching ref2VA checkpoint.
- Unexpected middle keyframe behavior: H3 only anchors true first/last frames through FL2VA; use ref2VA for middle pictures.
- Very long shot requested: keep each H3 generation within the trained range and split the project into editorial shots.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: krea-2-image](../krea-2-image/SKILL.md) · [Next skill: minimax-h3-turbo](../minimax-h3-turbo/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
