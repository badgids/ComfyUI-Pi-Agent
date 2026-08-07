# MiniMax H3 Turbo integration

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Scene Camera Action integration](scene-camera-action.md) · [Next: Dynamic integration context](dynamic-integration-context.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_END -->


ComfyUI-Pi includes lazily loaded operating knowledge for:

```text
https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo
```

The upstream pack is Apache-2.0 licensed. ComfyUI-Pi does not bundle its implementation, Turbo LoRA weights, or MiniMax H3 weights.

## What the pack does

MiniMax H3 Turbo modifies the standard MiniMax H3 joint video+audio pipeline so it can use a four-step starting profile.

It adds two public nodes:

```text
MiniMaxH3TurboLoRA
MiniMax-H3 Turbo LoRA
MODEL → MODEL

MiniMaxH3TurboSampler
MiniMax-H3 Turbo Sampler (4-step)
→ SAMPLER
```

The rest of the validated H3 graph stays structurally similar: conditioning, joint audio/video latent, decode, and audio/video mux remain H3 responsibilities.

## Correct Turbo wiring

Starting from an official/current H3 workflow or the installed Turbo example:

```text
H3 diffusion model loader
        ↓ MODEL
MiniMaxH3TurboLoRA
        ↓ MODEL
H3 guider / sampling model path
```

and:

```text
MiniMaxH3TurboSampler
        ↓ SAMPLER
SamplerCustomAdvanced
```

The documented starting scheduler profile is:

```text
BasicScheduler
scheduler = simple
steps = 4
```

Upstream documents values >=4 as valid, but four steps is the intended Turbo baseline.

## Why the custom sampler matters

MiniMax H3 jointly denoises video and audio, but they do not use the same flow schedule.

The upstream Turbo sampler uses:

```text
video shift = 12
audio shift = 3
```

A stock sampler steps both streams on one schedule. At around twenty steps that can be acceptable, but at four steps it can over-step the audio stream and produce distorted/blown-out sound.

Therefore ComfyUI-Pi treats this as a correctness rule:

> A four-step H3 Turbo workflow is not considered validated when the Turbo LoRA is paired with a stock single-schedule sampler.

## Turbo LoRA controls

### strength

Default:

```text
1.0
```

Public upstream guidance:

- blurry ghosting/smear → try a modest increase;
- over-sharp grain/artifacts → try a modest decrease.

ComfyUI-Pi treats these as tuning suggestions and requires output validation.

### low_vram

Upstream v1.2.2 adds:

```text
low_vram = false
```

Default/off:

- runtime-bypass LoRA;
- sharper result;
- higher peak VRAM.

On:

- merges LoRA updates into weights;
- lower peak VRAM;
- can be softer on quantized bases because small updates may be rounded during merging.

ComfyUI-Pi recommends `low_vram=true` primarily as an OOM recovery path, not as a free optimization.

## Base models

The current upstream release documents support for full and pruned/curve H3 bases, including:

```text
bf16
int8_convrot
pruned_int8
pruned_fp8
```

The upstream node handles pruned time-conditioning reinjection internally using its bundled grid. ComfyUI-Pi does not duplicate that implementation.

## H3 constraints still apply

Turbo changes sampling efficiency, not H3's basic shape/time rules.

The current public guidance includes:

```text
24 fps
width/height multiples of 32
17k+5 frame-count grid
124 frames ≈ 5 seconds
validated upstream range around 124–362 frames
```

Always validate the current installed H3 nodes/models when those constraints change upstream.

## Text-to-video

For T2V, `Pi MiniMax H3 Turbo Workflow` starts from the installed Turbo example workflow when available.

This is safer than recreating a current H3 graph from memory because official H3 schemas can change independently.

## Image-to-video and first/last frame

The Turbo model/sampler substitution also applies to H3 I2V.

When an installed example exposes `MiniMaxH3ImageToVideo`, ComfyUI-Pi can attach a normal `LoadImage` to the exact named `first_frame` and/or `last_frame` input discovered in that baseline.

It does not guess target input indexes when the named input cannot be found.

## Editing and repair

For an existing workflow, ComfyUI-Pi checks for:

- both Turbo nodes being present;
- `MiniMaxH3TurboSampler` feeding `SamplerCustomAdvanced`;
- the Turbo LoRA being in the H3 MODEL path;
- a `simple` scheduler starting profile;
- visible four-step configuration when safely inferable;
- a MiniMax H3-looking base model path;
- MiniMax CLIP loader configuration;
- a joint H3 audio/video latent path.

When exact widgets cannot be safely inferred from UI serialization, it warns and uses live `/object_info` instead of inventing a repair.

## Interaction with MiniMax H3 Director

ComfyUI-Pi treats **MiniMax H3 Turbo** and **MiniMax H3 Director** as two different integrations.

A Turbo request does not automatically load the Director manual.

A Director request does not automatically load the Turbo manual.

If the user explicitly asks to combine them, or a workflow contains nodes from both packs, both adapters may load. Pi must then inspect the actual model/guider/sampler/scheduler paths before claiming compatibility.

This prevents unnecessary context use and prevents assumptions based only on the shared H3 model family.

## Lazy loading behavior

At startup:

```text
minimax_h3_turbo.py adapter: NOT imported
Turbo guide: NOT injected
```

The compact adapter is loaded only when:

- the user explicitly asks about MiniMax H3 Turbo/H3 Turbo;
- the workflow contains `MiniMaxH3TurboLoRA` or `MiniMaxH3TurboSampler`; or
- a Turbo-specific ComfyUI-Pi node is called.

The complete bundled integration skill is reserved for explicit deep/tutorial requests.

## ComfyUI-Pi integration nodes

```text
Pi MiniMax H3 Turbo Status
Pi MiniMax H3 Turbo Plan
Pi MiniMax H3 Turbo Workflow
Pi Inspect MiniMax H3 Turbo Workflow
```

The general workflow analyzer and sidebar chat recognize the nodes automatically.

## Runtime authority

This integration was reviewed against upstream **v1.2.2**, commit `a7624b4c00626a8ae7e78860769389d706565190`, on 2026-08-07.

The user's installed pack, installed example workflow, live ComfyUI `/object_info`, and current MiniMax H3 core nodes remain authoritative if upstream changes.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Scene Camera Action integration](scene-camera-action.md) · [Next: Dynamic integration context](dynamic-integration-context.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_FOOTER_END -->
