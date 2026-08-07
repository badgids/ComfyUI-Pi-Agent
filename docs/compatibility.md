# Compatibility

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Architecture](architecture.md) · [Next: Known limitations](limitations.md)
<!-- DOC_NAV_END -->


## Python

Python 3.10 or newer.

## ComfyUI

The release uses the widely supported node registration mapping plus current frontend extension APIs defensively. Integration-specific workflow edits must still validate the user's live `/object_info` schemas because third-party node packs can change independently of ComfyUI-Pi.

## Platforms

Windows, Linux, macOS, WSL, Docker, and portable installations are supported when the underlying ComfyUI instance can read the repository and write the selected output directory.

## Optional tools

Pi, FFmpeg, Kdenlive, KJNodes, SageAttention, GGUF loaders, LTXVideo, model-specific custom nodes, and the supported third-party director packs are detected or documented but not bundled.

Missing optional integrations do not prevent ComfyUI-Pi from loading.

## ComfyUI-MiniMaxH3-Director

ComfyUI-Pi includes a first-class integration for the separately installed `seesee75-commits/ComfyUI-MiniMaxH3-Director` project.

At the time this release was prepared, upstream documentation identifies ComfyUI 0.30.0 or newer as a requirement for the Director pack. ComfyUI-Pi still checks the live runtime rather than assuming a particular future version behaves identically.

The adapter recognizes:

```text
MiniMaxH3DirectorCS
MiniMaxH3PreviewOverrideCS
MiniMaxH3RetakeStitchCS
MiniMaxH3EnhancePromptCS
```

New Director workflows use the installed upstream example workflow as the preferred baseline.

## WhatDreamsCost-ComfyUI

ComfyUI-Pi includes a first-class integration for `WhatDreamsCost/WhatDreamsCost-ComfyUI`.

The adapter recognizes:

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

Current upstream LTX Director documentation/release notes depend on current LTXVideo support and, for some workflows, KJNodes. The exact dependency set is selected from the installed upstream example workflow and live registered node classes rather than hardcoded as a universal requirement.

The upstream repository contains both distilled and GGUF LTX Director example workflows. ComfyUI-Pi selects the relevant installed example instead of performing a filename-only model-format substitution.

## ComfyUI-scene-camera-action

ComfyUI-Pi recognizes `SceneNode`, `ActingNode`, and `DirectingNode`. The adapter can author/validate SceneState JSON and create the public Scene → Acting → Directing chain, while leaving interactive motion/camera recording state to the upstream frontend. The node pack is MIT; its upstream `scene-staging-builder` skill declares Apache-2.0.

## ComfyUI-MiniMax-H3-Turbo

ComfyUI-Pi recognizes `MiniMaxH3TurboLoRA` and `MiniMaxH3TurboSampler`. The adapter expects the current H3 joint audio/video graph, Turbo sampler into `SamplerCustomAdvanced`, and the upstream `simple` four-step starting profile. The upstream project is Apache-2.0.

## Dynamic integration context

No integration guide is loaded into Pi at startup.

ComfyUI-Pi loads detailed node-pack context only when:

- the user names the integration;
- the current/attached workflow contains one of its node IDs; or
- an integration-specific node is explicitly called.

See [dynamic-integration-context.md](dynamic-integration-context.md).

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Architecture](architecture.md) · [Next: Known limitations](limitations.md)
<!-- DOC_NAV_FOOTER_END -->
