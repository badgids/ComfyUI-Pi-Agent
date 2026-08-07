# ComfyUI Scene Camera Action integration

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: WhatDreamsCost-ComfyUI integration](whatdreamscost-comfyui.md) · [Next: MiniMax H3 Turbo integration](minimax-h3-turbo.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_END -->


ComfyUI-Pi includes lazily loaded operating knowledge for:

```text
https://github.com/arturitu/ComfyUI-scene-camera-action
```

The upstream node pack is MIT licensed. Its included `scene-staging-builder` skill is Apache-2.0. ComfyUI-Pi does not copy the upstream implementation; it contains original GPL-3.0 compatibility metadata, validation logic, and operating guidance.

## What the pack does

Scene Camera Action is a 3D previz system inside ComfyUI. Its normal production chain is:

```text
SceneNode
Staging 3D Node
    ↓ SCENE
ActingNode
Acting 3D Node
    ↓ ACTING
DirectingNode
Directing 3D Node
    ├─ Captured Video
    └─ Captured Stage
```

It lets a user block out a 3D scene, record a human/car actor moving through that scene, then record camera cuts and export previz reference media.

## Nodes ComfyUI-Pi recognizes

### SceneNode — Staging 3D Node

Purpose:

- build/load/edit a 3D SceneState;
- place, group, duplicate, move, rotate, and scale staging assets;
- load scene presets;
- provide `SCENE` data to ActingNode.

The public backend schema has an optional `scene_data` JSON string and one `SCENE` output.

### ActingNode — Acting 3D Node

Purpose:

- receive staged scene data;
- select `human` or `car` actor type;
- set actor speed;
- record a movement path interactively;
- provide `ACTING` data to DirectingNode.

The upstream UI documents actor speed 1–20 and recording duration 4–15 seconds.

`motion_data` is interactive frontend state. ComfyUI-Pi treats it as frontend-managed instead of guessing its serialization.

### DirectingNode — Directing 3D Node

Purpose:

- receive acting/scene state;
- record camera cuts;
- use documented camera views such as TPV, FPV, Wide, and Side;
- output a captured previz `VIDEO` and initial-frame/stage `IMAGE`.

`directing_data` is frontend-managed camera-timeline state. ComfyUI-Pi does not fabricate it from guessed widget indexes.

## Natural-language scene staging

The upstream repository includes a `scene-staging-builder` skill. ComfyUI-Pi understands the same public scene contract but keeps an original compact procedure in its own GPL-3.0 skill library.

For normal scene-generation requests, Pi receives only the relevant staging rules. The full internal guide is loaded only for an explicit comprehensive tutorial/deep-dive request.

Important SceneState rules include:

```text
root.type = cube_scene
root.nodes = [...]
```

Generated blockout geometry uses:

```text
block
 group
```

and transforms:

```text
px py pz
rx ry rz
sx sy sz
```

### Coordinate system

```text
X = left/right
Y = vertical
Z = depth
Y=0 = staging ground
```

The viewport already provides its floor. ComfyUI-Pi will not add a giant floor block simply to represent ground.

For a non-rotated box that sits directly on the ground, the position is its center, so a useful alignment rule is:

```text
py = sy / 2
```

### Spawn points

When actor placement matters, SceneState can include:

```json
{
  "spawn_point": {
    "px": 0.0,
    "py": 0.0,
    "pz": 5.0,
    "ry": 0.0
  }
}
```

If the actor starts on an elevated platform, `py` should match the top of the supporting surface, not the platform's center.

## Actor-aware staging

ComfyUI-Pi knows the public upstream defaults used by the staging skill.

For cars, useful starting clearances include:

- roads around 4m or wider;
- ramps around 10–25 degrees;
- overpass clearance around 3.5m or more.

For humans, useful starting proportions include:

- door width around 1.2m;
- door height around 2.2m;
- stair rise around 0.25m;
- stair depth around 0.5m.

These are layout defaults, not mandatory creative values. The user's real reference or scene requirements take priority.

## Creating a workflow

`Pi Scene Camera Action Workflow` creates a safe base chain from the pack's public sockets:

```text
SceneNode → ActingNode → DirectingNode
```

The generated workflow does **not** fake an actor recording or camera-cut recording. Those states remain blank until the user creates them using the upstream interactive widgets.

The workflow node reports whether the actual upstream pack is installed. A generated graph may be structurally useful while still being marked non-runnable if the pack is missing.

## Editing a SceneState preset

For a request such as:

```text
Move the warehouse door two meters left and widen it.
```

Pi should:

1. read the existing SceneState JSON;
2. locate the exact node/group by id or name;
3. change only the requested transforms;
4. preserve unrelated ids/groups;
5. check numeric transforms and ground alignment;
6. validate the JSON;
7. preserve the original unless replacement was approved.

## Editing a workflow

For normal graph edits:

1. inspect the active workflow;
2. confirm Scene/Acting/Directing node IDs;
3. query live `/object_info` when available;
4. edit only validated sockets/widgets;
5. leave opaque recording state to the upstream frontend;
6. validate the resulting graph.

## Using previz downstream

The `Captured Stage` image and `Captured Video` are reference assets. They can be used in later pipelines such as:

- V2V generation;
- I2V keyframe/reference workflows;
- motion reference planning;
- shot continuity review;
- storyboard/shot comparison;
- production tutorial examples.

The original pack mentions workflows such as HunyuanVideo, Wan, and AnimateDiff as examples. ComfyUI-Pi should route downstream generation based on what is actually installed rather than hardcoding one generator.

## Lazy loading behavior

At ComfyUI-Pi startup:

```text
scene_camera_action.py adapter: NOT imported
full Scene Camera Action guide: NOT injected
full scene-staging skill: NOT injected
```

A compact integration context is loaded only when:

- the user says Scene Camera Action/Staging 3D/Acting 3D/Directing 3D/etc.;
- the active/attached workflow contains `SceneNode`, `ActingNode`, or `DirectingNode`; or
- a Scene Camera Action-specific ComfyUI-Pi node is called.

This preserves the sparse-context policy.

## ComfyUI-Pi integration nodes

```text
Pi Scene Camera Action Status
Pi Scene Camera Action Plan
Pi Scene Camera Action Workflow
Pi Inspect Scene Camera Action Workflow
```

The general `Pi Analyze Workflow` and sidebar chat also recognize the pack automatically.

## Runtime authority

This integration was reviewed against upstream **v0.3.0**, commit `9d572b46262ec2b90fa1116380c11d16de7e6d5d`, on 2026-08-07.

The installed node pack, live ComfyUI schemas, installed presets, and current frontend always override this static documentation when upstream changes.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: WhatDreamsCost-ComfyUI integration](whatdreamscost-comfyui.md) · [Next: MiniMax H3 Turbo integration](minimax-h3-turbo.md) · [All integrations](index.md#first-class-node-pack-integrations)
<!-- DOC_NAV_FOOTER_END -->
