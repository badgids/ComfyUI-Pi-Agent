# WhatDreamsCost-ComfyUI integration

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: MiniMax H3 Director integration](minimax-h3-director.md) · [Next: Scene Camera Action integration](scene-camera-action.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_END -->


ComfyUI-Pi has built-in, lazily loaded operating knowledge for the public **WhatDreamsCost-ComfyUI** node pack.

Upstream project:

```text
https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
```

Upstream license: **GPL-3.0**.

ComfyUI-Pi is also GPL-3.0.

The integration does not load into Pi's context until the user asks about this pack or a matching node is found in the attached/current workflow.

## Nodes ComfyUI-Pi recognizes

```text
LTXDirector
LTXDirectorGuide
LTXDirectorCropGuides
LTXKeyframer
MultiImageLoader
LTXSequencer
SpeechLengthCalculator
LoadAudioUI
LoadVideoUI
```

These are the public node IDs exported by the upstream package at the time this release was prepared.

## LTX Director

`LTXDirector` is the main timeline editor.

ComfyUI-Pi understands that its current feature set includes:

- timeline-based LTX video generation;
- text-to-video;
- image-to-video;
- multiple prompt segments;
- Prompt Relay;
- first, middle, and last-frame guidance;
- imported video segments and video extension;
- IC-LoRA reference media;
- custom audio;
- audio inpainting;
- Retake Mode;
- timeline save/load;
- model caching and performance optimizations;
- SageAttention/Triton-aware workflows when the installed dependencies support them.

## Important Director inputs and outputs

The current upstream schema exposes inputs including:

```text
model
clip
audio_vae
optional_latent
global_prompt
start_second
end_second
duration_seconds
start_frame
end_frame
duration_frames
timeline_data
use_custom_audio
use_custom_motion
inpaint_audio
local_prompts
segment_lengths
epsilon
frame_rate
display_mode
guide_strength
custom_width
custom_height
resize_method
divisible_by
img_compression
override_audio
```

Outputs include:

```text
model
positive
video_latent
audio_latent
guide_data
motion_guide_data
frame_rate
combined_audio
```

The installed live schema remains the authority.

## Do not hand-edit timeline state by guessed indexes

Several important values are controlled by the Director's frontend:

```text
timeline_data
local_prompts
segment_lengths
guide_strength
```

ComfyUI-Pi should not guess positions inside `widgets_values`.

For timeline changes, use the Director frontend or a version-aware adapter that has validated the exact installed schema.

This rule matters when Pi is asked to:

- add or remove shots;
- change shot timing;
- move guide frames;
- mark an end frame;
- add IC-LoRA media;
- add or trim audio;
- change Retake Mode.

## Prompt Relay

LTX Director integrates Prompt Relay for multi-segment prompting.

ComfyUI-Pi understands the distinction between:

- a single-prompt workflow, where current upstream code can use a faster path without the attention mask;
- a multi-prompt timeline, where segment lengths and Prompt Relay boundaries matter.

Do not apply MiniMax H3 storyboard rules to LTX Prompt Relay. They are different conditioning systems.

## LTX frame rule

When the current Director auto-generates an LTXV latent, upstream code uses the LTXV temporal rule:

```text
8n + 1 frames
```

This must not be confused with MiniMax H3 Director's `17k+5` rule.

## Guide frames

LTX Director supports first, middle, and last-frame guidance.

The timeline can mark an image segment as an end frame. Guide position, guide strength, timeline range, resize settings, and final dimensions should be preserved during edits.

## Custom audio and audio inpainting

The pack supports custom timeline audio and audio inpainting.

ComfyUI-Pi keeps these concepts separate:

```text
generated audio
custom imported timeline audio
audio inpainting
audio from a video/reference track
combined_audio output
final NLE mix/stems
```

Pi should not silently replace one with another.

## IC-LoRA

Current upstream releases support LTX IC-LoRA workflows and reference images/video through the Director timeline.

When a user asks for IC-LoRA:

1. inspect the installed upstream workflow;
2. verify the required LTXVideo and KJNodes node classes are registered;
3. preserve the media's intended reference role;
4. validate model/LoRA compatibility before execution.

## Retake Mode

Retake Mode regenerates a selected region of an existing video.

ComfyUI-Pi should preserve:

- the base video;
- the selected region;
- surrounding continuity;
- prompt changes;
- audio policy;
- the original version before repair/regeneration.

## GGUF support

The upstream repository currently provides a dedicated LTX Director GGUF example workflow.

When the user requests GGUF, ComfyUI-Pi should use that installed GGUF example as the starting point.

It should **not** take a safetensors workflow and simply change a filename extension.

A GGUF conversion may require different:

- model loaders;
- text-encoder loaders;
- LoRA/patch paths;
- custom-node dependencies.

Use live schemas and validate the completed graph.

## Workflow creation

The `Pi WhatDreamsCost Workflow` node follows this policy:

1. Find the installed WhatDreamsCost-ComfyUI pack.
2. List its installed `example_workflows`.
3. Select the closest upstream example.
4. Copy that workflow into the user's project rather than modifying the upstream file.
5. Attach the user's requested plan as ComfyUI-Pi metadata.
6. Inspect the graph.
7. Use live node schemas for safe typed changes.
8. Leave frontend-managed timeline state to the Director UI unless a validated adapter can change it safely.

Supported starting selections include:

```text
director
custom_audio
fflf_2_stage
fflf_3_stage
```

and:

```text
auto
safetensors
gguf
```

If the pack is not installed, the node returns a precise missing-dependency result rather than creating a fake graph.

## Utility nodes

### Multi Image Loader

Use for loading and ordering multiple images and feeding compatible image/guide workflows. Do not assume it requires LTX Director.

### LTX Sequencer

Use for sequence/guide construction and first/middle/last-frame workflows. The upstream project recommends it over the older Keyframer for many use cases.

### LTX Keyframer

Recognize and preserve existing workflows that use it. Validate its current live inputs before editing.

### Load Video UI

Interactive video import, trim, resize, crop, preview, and file-selection behavior. Its frontend state should be preserved when converting workflows.

### Load Audio UI

Interactive audio import/trim behavior. Keep its file and timing state intact.

### Speech Length Calculator

Can help estimate target duration from dialogue. Treat its result as planning input; the target video model's actual duration/frame rules still apply.

## Dedicated ComfyUI-Pi nodes

```text
Pi WhatDreamsCost Status
Pi WhatDreamsCost Plan
Pi WhatDreamsCost Workflow
Pi Inspect WhatDreamsCost Workflow
```

The general `Pi Analyze Workflow` node also attaches a WhatDreamsCost-specific report when it detects these nodes.

## Sidebar chat

A user can simply attach the current workflow and ask:

```text
Explain this LTX Director workflow.
```

or:

```text
Make a safe plan to add IC-LoRA reference video and custom audio to this workflow.
```

The WhatDreamsCost knowledge is loaded for that request only.

## Compatibility discipline

The upstream pack changes over time. Built-in knowledge is a guide, not a frozen replacement for upstream.

For every real edit:

- inspect the user's installed version;
- inspect `/object_info`;
- inspect the current workflow;
- prefer the installed upstream example;
- preserve the original workflow;
- return a diff and warnings.


## Source freshness

The bundled knowledge in ComfyUI-Pi v0.1.8 was reviewed against upstream WhatDreamsCost-ComfyUI **2.0.4**, commit `a3c809c8b593a74c2ddcd6c1f83ad85ebebe3c64`, on 2026-08-06. The installed pack, its example workflows, and live ComfyUI schemas remain authoritative if a newer version is present.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: MiniMax H3 Director integration](minimax-h3-director.md) · [Next: Scene Camera Action integration](scene-camera-action.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_FOOTER_END -->
