---
name: minimax-h3-turbo
license: GPL-3.0
version: 1.0.0
---

# MiniMax H3 Turbo integration procedure

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: minimax-h3-director](../minimax-h3-director/SKILL.md) · [Next skill: moodboard](../moodboard/SKILL.md)
<!-- DOC_NAV_END -->


Use this procedure only for **ComfyUI-MiniMax-H3-Turbo**, `MiniMaxH3TurboLoRA`, `MiniMaxH3TurboSampler`, or an explicit H3 Turbo workflow request.

## Goal

Create, inspect, edit, repair, or explain a MiniMax H3 Turbo workflow without disturbing the validated H3 joint video/audio structure.

## Required Turbo path

1. Begin from the installed Turbo example workflow or a current official MiniMax H3 T2V/I2V workflow.
2. Insert `MiniMaxH3TurboLoRA` in the MODEL path after the H3 diffusion model loader.
3. Feed the resulting model to the normal H3 guider/sampling path.
4. Feed `MiniMaxH3TurboSampler` into `SamplerCustomAdvanced`.
5. Use `BasicScheduler` with scheduler `simple` and 4 steps as the starting profile.
6. Preserve MiniMax H3 conditioning, joint video/audio latent construction, video/audio VAE decode, and final audio/video mux unless the task explicitly changes them.
7. Validate with live `/object_info` and the installed example before modifying exact widget serialization.

## Why the Turbo sampler is mandatory at four steps

MiniMax H3's video and audio streams use different flow schedules. The upstream Turbo implementation uses video shift 12 and audio shift 3. A stock single-schedule sampler may over-step the audio stream at four steps, producing distorted or blown-out audio. Do not call a four-step workflow validated when the Turbo LoRA is paired with the wrong sampler.

## LoRA controls

- Default strength: `1.0`.
- Upstream guidance: if the result is blurry/smeared/ghosted, try a modest strength increase; if it is over-sharp or grainy, try a modest decrease.
- `low_vram = false` is the default runtime-bypass path: sharper, more peak VRAM.
- `low_vram = true` merges the LoRA for lower peak VRAM: useful for OOM recovery, but potentially softer on quantized bases.

Never treat these quality adjustments as guarantees; validate actual output.

## Base/model constraints

Upstream v1.2.2 documents support for full H3 bases (including bf16/int8_convrot) and pruned/curve bases (including pruned int8/fp8). The node handles the pruned time-conditioning reinjection internally.

Turbo does not change H3's basic temporal/spatial constraints:

- 24 fps.
- Width/height multiples of 32.
- Frame counts on the 17k+5 grid (about 124 frames for ~5 seconds).

## T2V / I2V / FLF

The Turbo substitution applies to the shared H3 model/sampler path. For image-to-video or first/last-frame use, preserve the current `MiniMaxH3ImageToVideo` conditioning path and attach images to the exact live first/last frame sockets. Do not invent target slots when live schema information is available.

## Interaction with other H3 packs

Do not assume automatic compatibility with MiniMax H3 Director or another H3 wrapper. If combining them, inspect the actual model, guider, sampler, scheduler, and latent path first. Load the other integration's knowledge only when its nodes or explicit user request require it.

## Completion evidence

Report the two Turbo nodes, scheduler/step configuration, LoRA strength/low-VRAM mode, base H3 model path, joint audio/video decode path, and validation performed. Never claim four-step audio is correct without verifying the Turbo sampler path.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: minimax-h3-director](../minimax-h3-director/SKILL.md) · [Next skill: moodboard](../moodboard/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
