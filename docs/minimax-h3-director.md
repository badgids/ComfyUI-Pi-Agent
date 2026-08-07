# MiniMax H3 Director integration

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Music, speech, and audio profiles](audio-music-voice.md) · [Next: WhatDreamsCost-ComfyUI integration](whatdreamscost-comfyui.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_END -->


ComfyUI-Pi has built-in interoperability knowledge for **ComfyUI-MiniMaxH3-Director** by `seesee75-commits`.

Upstream project:

```text
https://github.com/seesee75-commits/ComfyUI-MiniMaxH3-Director
```

The Director pack is a ComfyUI timeline editor for MiniMax H3. It turns timeline segments, first/last frames, image references, reference video, reference audio, and sound choices into the conditioning needed by MiniMax H3.

This integration lets ComfyUI-Pi:

- recognize Director workflows automatically;
- explain how a Director workflow works;
- inspect a workflow for common mistakes;
- choose between the FL2VA and ref2VA paths;
- create a Director workflow from the **installed Director pack's own example workflow**;
- plan edits without guessing private frontend state;
- help from either Pi nodes or the Pi Agent sidebar chat;
- include Director workflows in complete productions and tutorials.

## Licensing boundary

ComfyUI-MiniMaxH3-Director is licensed **GPL-3.0** upstream. ComfyUI-Pi is GPL-3.0 licensed.

ComfyUI-Pi therefore does **not** copy, vendor, translate, or bundle the Director pack's Python or JavaScript source. It also does not bundle a copied upstream example workflow.

The ComfyUI-Pi integration is original interoperability code. It works through:

- the Director pack's public registered node IDs;
- live ComfyUI node schemas when available;
- installed filenames and model inventory;
- the Director pack's own example workflows when the pack is installed;
- a small original capability profile that records the public operating rules Pi needs to reason correctly.

The GPL-3.0 license continues to apply to the Director pack itself. See [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Automatic detection

ComfyUI-Pi recognizes these public node IDs:

```text
MiniMaxH3DirectorCS
MiniMaxH3PreviewOverrideCS
MiniMaxH3RetakeStitchCS
MiniMaxH3EnhancePromptCS
```

The Director Chain code may exist in an upstream checkout, but it is intentionally not treated as a usable registered production node unless a future installed release actually registers it.

ComfyUI-Pi looks for the Director pack without using personal machine paths. It can discover it from:

1. `COMFYUI_MINIMAX_H3_DIRECTOR_PATH`, when explicitly set;
2. live ComfyUI node registration;
3. the normal sibling `custom_nodes` directory where both repositories are commonly cloned;
4. ComfyUI's registered custom-node paths when exposed by `folder_paths`.

Nothing is downloaded during ComfyUI-Pi import.

## The two MiniMax H3 paths

This distinction is critical.

| Director mode | Model family | Use it for |
|---|---|---|
| Refs OFF | FL2VA | text-to-video, first-frame, last-frame, first+last-frame generation |
| Refs ON | ref2VA | character references, extra images, reference video, reference audio |

The diffusion checkpoints are separate model trainings. They are not interchangeable just because both filenames contain `MiniMax-H3`.

Typical filename roles are:

```text
minimax_h3_fl2va_*     -> FL2VA / Refs OFF diffusion model
minimax_h3_ref2va_*    -> ref2VA / Refs ON diffusion model
```

ComfyUI-Pi treats the filename only as evidence. When it is operating a live installation it should prefer the live node schema, current installed model inventory, and the user's explicitly selected model.

## Required model roles

A typical Director workflow needs these roles:

```text
FL2VA diffusion model
ref2VA diffusion model                 optional when references are never used
Qwen3-VL MiniMax text encoder
MiniMax H3 video VAE
MiniMax H3 audio VAE                   required for audio reference / normal joint AV decode
```

The text encoder must be loaded through a `CLIPLoader` configured with:

```text
type = minimax
```

ComfyUI-Pi's Director inspector warns when it sees a `CLIPLoader` but cannot see a `minimax` loader type.

## Director timeline tracks

The Director timeline represents different media differently depending on the selected reference path.

### Main track

Prompt segments become shots in the compiled storyboard prompt.

In FL2VA mode:

- an appropriate image at the beginning becomes a first-frame anchor;
- an appropriate end image becomes a last-frame anchor;
- H3 only uses the beginning and end anchor positions for this conditioning path.

In ref2VA mode, timeline images can become numbered picture references instead.

### Reference-video track

Video placed on the reference-video track becomes a MiniMax video reference in ref2VA mode.

### Audio track

Audio can become a MiniMax audio reference in ref2VA mode. The Director can also expose its timeline mix as `combined_audio` for the final video mux.

MiniMax H3 generates audio jointly with video. Do not reason about the Director as though it were an ordinary video model followed by a completely independent audio-generation node.

## Reference limits

ComfyUI-Pi carries the Director pack's documented MiniMax H3 reference limits as validation knowledge:

```text
Reference images:          at most 9
Reference videos:          at most 3
Each reference video:      2 to 15 seconds
All reference video time:  at most 15 seconds total
Reference audio clips:     at most 3
All reference files:       at most 12 total
```

Character-slot images and additional `ref_images` share the image-reference budget.

The planner warns before creating a request that exceeds these limits. The workflow inspector also looks at serialized timeline metadata when it is safely available.

## Duration and frame grid

MiniMax H3 output is planned around:

```text
24 fps
roughly 4 to 15 seconds per trained generation window
17k + 5 valid output-frame grid
```

A requested duration therefore may be rounded upward to the next valid frame count.

For example, a nominal five-second window is not necessarily exactly 120 output frames after H3 alignment.

ComfyUI-Pi does not use an unavailable Director Chain node to pretend long-form generation is solved. A longer film should be divided into real shots or generation windows and then assembled by the production compiler and NLE handoff system.

## Canvas rules

Useful starting knowledge for the Director is:

```text
native short edge: about 768 px
maximum common native canvas area: around 768 x 1344
width and height alignment: divisible by 32
```

The installed Director node remains the authority for actual canvas adaptation. ComfyUI-Pi should not bypass its resize behavior by blindly forcing dimensions.

## Prompt formats

The Director can compile its timeline into MiniMax-oriented storyboard text.

Important semantics include:

- the first shot is `[Shot 1]` without a cut timestamp;
- later shots use a strictly increasing `MM:SS.mmm` cut time;
- reusable subjects can be defined in terms of concrete picture references;
- soundscape and non-diegetic music are separate concepts;
- empty structural sections should not be created just to fill a template.

A simplified structure can look like:

```text
subject_definitions: ...

retention_analysis: ...

detailed_description: [Shot 1] ... [Shot 2] At 00:03.500, ...

overall_soundscape: ...

non_diegetic_music: ...
```

The Director can also use the ComfyUI-style timed range notation used by MiniMax H3 templates.

ComfyUI-Pi does not rewrite the Director's compiled prompt behind its back. When a user asks Pi to improve a prompt, Pi should respect whichever prompt format the current Director timeline is configured to compile.

## Character references

The Director supports three convenient character slots, commonly referenced as:

```text
@char1
@char2
@char3
```

In ref2VA mode the character slot images participate in actual image-reference conditioning and the Director resolves the numbering.

In FL2VA mode an optional locally analyzed text description can give the prompt a textual description of the character even though the image is not being passed through ref2VA.

ComfyUI-Pi should never invent `<Picture N>` or `<Subject N>` numbers independently of the Director. The Director owns the final reference numbering.

## MiniMax H3 Enhance Prompt

`MiniMaxH3EnhancePromptCS` uses a local vision-capable language model to turn a short idea plus reference images into H3-oriented prompt text.

The upstream node supports local/OpenAI-compatible endpoints such as Ollama or LM Studio. This is optional and is not required for ordinary Director operation.

Important rule: when the Enhance node is creating a **global** prompt, it should not create its own Director structural section labels or numbered reference tags. The Director adds the final structure and numbering.

ComfyUI-Pi therefore treats Enhance Prompt as a helper before the Director, not as a replacement for Director prompt compilation.

## Preview Override

`MiniMaxH3PreviewOverrideCS` can sit between the Director model output and the sampler so the user can see the whole evolving shot instead of only an ordinary single-frame latent preview.

A useful conceptual graph is:

```text
Director.model
    -> MiniMax H3 Preview Override
    -> BasicGuider / sampler path
```

The preview is optional. A workflow remains conceptually valid without it.

Some preview targets may use VideoHelperSuite for a player. ComfyUI-Pi must not declare VideoHelperSuite mandatory for the entire Director pack when only that optional preview mode needs it.

## Sampling starter profile

The upstream example workflow provides a sensible starting point:

```text
sampler:    res_multistep
scheduler:  simple
steps:      about 20
guider:     BasicGuider
CFG:        no ordinary CFG path
```

For reference-heavy ref2VA work, alternative scheduler behavior may be useful. These values are starting profiles, not universal creative laws.

When editing a real workflow, ComfyUI-Pi should preserve a user's working sampler choices unless the user asks for a change or validation finds a concrete incompatibility.

## Joint video and audio decode

The Director outputs a joint MiniMax H3 latent.

A normal downstream decode concept is:

```text
joint latent
  |-> VAEDecode       + video VAE -> images
  |-> VAEDecodeAudio  + audio VAE -> audio

images + audio + fps
  -> CreateVideo
```

Using the wrong VAE for the wrong latent component is a real workflow error. ComfyUI-Pi should preserve the separate video-VAE and audio-VAE roles.

## Retake mode

`MiniMaxH3RetakeStitchCS` supports the Director's retake workflow.

Conceptually:

1. choose a range in an existing base video;
2. the Director regenerates that range using surrounding frames as anchors;
3. the Director returns `retake_info`;
4. Retake Stitch combines the unchanged base material and the regenerated range.

A retake request should not cause ComfyUI-Pi to regenerate unrelated shots in a complete project.

## How ComfyUI-Pi creates Director workflows

ComfyUI-Pi deliberately does **not** hand-author a fake copy of the Director's complex timeline JSON.

When the Director pack is installed, `Pi MiniMax H3 Director Workflow`:

1. locates the installed Director pack;
2. finds its own current example workflows;
3. chooses the most appropriate available example as a baseline;
4. copies the workflow data into the output object;
5. adds only ComfyUI-Pi provenance/planning metadata;
6. validates the result using ComfyUI-Pi's workflow analyzer and Director-specific inspector.

This has two benefits:

- the workflow starts from a graph maintained by the Director project itself;
- ComfyUI-Pi does not copy GPL workflow/code into its GPL-3.0 repository.

When the Director pack is not installed, ComfyUI-Pi reports that the integration is unavailable instead of fabricating a graph with guessed node schemas.

## How ComfyUI-Pi edits Director workflows safely

The Director node contains frontend-managed timeline state. Editing arbitrary indexes inside `widgets_values` is fragile and can corrupt a timeline.

Therefore ComfyUI-Pi follows these rules:

### Safe automatic edits

Pi may safely plan or make changes such as:

- replace a loader model with another validated compatible installed model;
- repair a missing external connection when live socket types prove the connection;
- add or remove surrounding ordinary ComfyUI utility nodes;
- preserve or replace an optional Preview Override;
- repair video/audio VAE routing;
- create a fresh workflow from the installed upstream example;
- add notes/groups/provenance without changing Director timeline semantics.

### Director-owned timeline edits

Shot segments, timeline media, character slots, prompt zones, retake ranges, and similar state should normally be edited through the Director's own ComfyUI frontend controls.

When Pi is asked to modify those areas, it should:

1. explain the intended timeline change;
2. inspect current serialized state when available;
3. prefer the Director's own UI or a documented live API if one exists;
4. never guess undocumented `widgets_values` indexes;
5. validate after the user or supported adapter applies the change.

This is intentionally conservative. A working timeline is more valuable than an aggressive edit that silently breaks the Director frontend state.

## Dedicated ComfyUI-Pi nodes

Four ComfyUI-Pi nodes provide the integration directly:

### Pi MiniMax H3 Director Status

Reports whether the Director pack is installed, which public nodes are registered, where its examples were discovered, and the bundled compatibility profile.

### Pi MiniMax H3 Director Plan

Creates a structured plan from:

- requested mode;
- duration;
- prompt format;
- reference counts;
- preview choice;
- Enhance Prompt choice;
- retake choice.

`auto` chooses ref2VA when actual reference media is requested and FL2VA otherwise.

### Pi MiniMax H3 Director Workflow

Creates a workflow by cloning an **installed upstream example workflow** and attaching a ComfyUI-Pi plan. It fails clearly when no installed upstream example can be found.

### Pi Inspect MiniMax H3 Director Workflow

Inspects a supplied workflow for Director-specific requirements and common mistakes.

## Sidebar chat

No special node is required to ask Pi about the Director pack.

Examples:

```text
Explain this MiniMax H3 Director workflow.

Why does this workflow need both FL2VA and ref2VA models?

Create a MiniMax H3 Director workflow for a 7 second shot with two character references.

Check the current Director workflow for model, VAE, and reference mistakes.

I want to use this storyboard as three H3 shots. Plan the Director workflows.

The current shot is in Refs ON mode. Tell me whether my references exceed H3's limits.
```

When the current ComfyUI workflow contains a Director node, or the user's message clearly asks about MiniMax H3 Director, the Pi runtime lazily loads this integration context for that request. The guide is not injected at ComfyUI/Pi startup and unrelated requests receive none of it.

## Complete productions

The Complete Production compiler can treat Director workflows as a video-generation target.

For longer projects it should use the production structure already provided by ComfyUI-Pi:

```text
screenplay
 -> scene list
 -> shot list
 -> storyboard
 -> one or more Director generation windows per shot as appropriate
 -> generated video/audio clips
 -> editorial media
 -> Kdenlive/OTIO handoff
```

This keeps the MiniMax H3 trained generation window separate from the length of the final movie.

## Tutorials

The Tutorial Compiler can recognize Director nodes and include their integration inspection in the workflow analysis.

A Director tutorial should explain, at minimum:

- FL2VA versus ref2VA;
- model and VAE roles;
- timeline tracks;
- first/last-frame behavior;
- reference limits;
- prompt format;
- sampling and joint AV decode;
- optional preview;
- optional Enhance Prompt;
- retakes;
- how the output is handed to the next project stage.

## GGUF policy

ComfyUI-Pi's general model system understands GGUF where a compatible installed loader is available and validated.

The MiniMax H3 Director integration does **not** assume that a GGUF file can replace an upstream Director safetensors checkpoint merely because the model family name matches.

A Director GGUF substitution may be offered only when the live ComfyUI installation exposes a compatible MiniMax H3 GGUF loader and the complete component/LoRA/reference path can be validated. Otherwise Pi reports the GGUF candidate as unavailable or unvalidated and keeps the known working format.

## Common problems Pi should recognize

### Director node is missing

The upstream custom node pack is not installed, did not import, or the browser needs a hard refresh after installation.

### CLIP input fails or output is nonsense

Check that `CLIPLoader` is using type `minimax` and the correct MiniMax H3 Qwen3-VL text encoder.

### Refs ON uses the wrong checkpoint

Use the ref2VA checkpoint for the reference-conditioning path.

### Refs OFF uses the wrong checkpoint

Use the FL2VA checkpoint for text and first/last-frame conditioning.

### Reference request is silently incomplete

Check the image, video, audio, total-file, and video-duration limits before rendering.

### Audio-reference workflow fails

Make sure the audio VAE is connected when the selected path needs audio references.

### Video is bad while audio appears valid

Verify that the video latent is decoded with the video VAE and the audio portion with the audio VAE.

### A middle image did not behave like a keyframe

FL2VA first/last-frame conditioning anchors the ends, not an arbitrary middle timeline frame. Use the correct reference path when the image is intended as a reference rather than an endpoint anchor.

### Long project needs more than one generation

Split it into production shots or windows and assemble the finished clips in the NLE. Do not rely on an unregistered Chain node.

## Source freshness

The bundled knowledge in ComfyUI-Pi v0.1.8 was reviewed against upstream MiniMax H3 Director **0.1.5**, commit `ac5c389aac1e2db6ca567457f3d3217a77ee3c61`, on 2026-08-06. The installed pack and live ComfyUI schemas remain authoritative if a newer version is present.

Because custom nodes evolve, ComfyUI-Pi always treats live ComfyUI schemas and the user's installed Director example workflows as more authoritative than static bundled assumptions.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Music, speech, and audio profiles](audio-music-voice.md) · [Next: WhatDreamsCost-ComfyUI integration](whatdreamscost-comfyui.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_FOOTER_END -->
