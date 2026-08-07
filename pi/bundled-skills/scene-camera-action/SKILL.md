---
name: scene-camera-action
license: GPL-3.0
version: 1.0.0
---

# Scene Camera Action integration procedure

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: reference-asset-system](../reference-asset-system/SKILL.md) · [Next skill: screenplay-breakdown](../screenplay-breakdown/SKILL.md)
<!-- DOC_NAV_END -->


Use this procedure only when the user asks about **ComfyUI-scene-camera-action**, its `SceneNode`, `ActingNode`, `DirectingNode`, its SceneState presets, or a 3D previz workflow that clearly uses this pack.

## Goal

Help the user create, inspect, edit, repair, or explain a Scene Camera Action project while keeping the pack's interactive frontend state authoritative.

## Required order

1. Inspect the installed live node schemas when available.
2. Identify whether the task concerns staging, acting, directing, or all three.
3. For a complete previz chain, use `SceneNode → ActingNode → DirectingNode`.
4. For SceneState creation/editing, preserve the existing JSON structure and stable ids.
5. Let the upstream frontend record actor motion and camera-cut timeline state; do not invent opaque `motion_data` or `directing_data` serialization.
6. Validate the resulting workflow/preset before claiming success.

## SceneState authoring

Generated staging geometry should follow the upstream pack's public spatial contract:

- Root object: `type: "cube_scene"` with a `nodes` array.
- Use `block` and `group` nodes for generated blockout geometry.
- Every generated scene node needs a stable `id`, `type`, `name`, and `transform` using numeric `px, py, pz, rx, ry, rz, sx, sy, sz`; a `group` stores child scene nodes in `children`.
- Treat X as left/right, Y as vertical, Z as depth.
- The viewport already has its ground/floor at Y=0. Do not add a floor block just to represent ground.
- A non-rotated ground-resting box centers vertically at approximately `py = sy / 2`.
- Use logical groups for compound forms.
- Include `spawn_point {px, py, pz, ry}` when actor placement matters. On an elevated platform, set spawn `py` to the top supporting surface rather than inside it.
- Keep generated content inside the pack's documented 100×100 meter working area unless the installed pack or user requires otherwise.

## Actor-aware staging

For a car, leave practical road, turn, ramp, and overhead clearance. The upstream public skill documents a 4m minimum road width, roughly 10–25 degree ramps, and at least 3.5m overpass clearance as useful defaults.

For a human, leave human-scale doors, stairs, paths, and room clearance. Do not force these defaults when the user's reference/project requires another scale.

## Acting

`ActingNode` accepts the scene plus `actor_type` (`human` or `car`), speed, duration, and frontend-managed motion data. The upstream UI documents approximately 4–15 seconds for the duration control. Use the pack's widget to record motion instead of fabricating the recording payload.

## Directing

`DirectingNode` consumes acting data and frontend-managed camera timeline state. The public pack documents TPV, FPV, Wide, and Side camera modes. It outputs a captured previz video and a captured stage image; these are useful reference assets for later V2V/I2V/video-generation workflows.

## Editing policy

When editing a SceneState preset:

1. Parse and validate the current JSON.
2. Identify exact target node/group ids or names.
3. Apply the smallest requested transform/add/delete change.
4. Recheck numeric transforms, ids, group children, ground/clearance behavior, and spawn point.
5. Preserve the original file unless the user explicitly approved replacement.

When editing the ComfyUI graph, use live sockets and do not guess frontend widget indices.

## Completion evidence

Report which preset/workflow changed, what nodes or scene objects changed, whether the pack was detected, and what validation was performed. If interactive recording is still required, say so instead of claiming the previz is finished.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../../../README.md) · [Documentation home](../../../docs/index.md) · [Skills index](../README.md) · [Previous skill: reference-asset-system](../reference-asset-system/SKILL.md) · [Next skill: screenplay-breakdown](../screenplay-breakdown/SKILL.md)
<!-- DOC_NAV_FOOTER_END -->
