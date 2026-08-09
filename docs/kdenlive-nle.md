# Kdenlive and NLE handoff

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: ComfyUI-native tutorial compiler](tutorials.md) · [Next: Security and path policy](security.md)
<!-- DOC_NAV_END -->


## Default target

Kdenlive is the default NLE. The package also contains portable timeline data so another editor or a later adapter can rebuild the sequence.

## Input manifest

The node reads `title`, `profile`, `shots`, and `assets`. A shot can reference an asset ID or direct media path and should include a duration.

## Generated files

- `.kdenlive` MLT XML;
- OTIO-style JSON;
- `timeline.json`;
- `media-map.json`;
- `project-profile.json`;
- Markdown and DOCX assembly guides.

## Conservative writer

The writer creates a basic main-picture playlist. Finish titles, effects, transitions, audio mixing, nested sequences, and version-specific features in Kdenlive.

## Placeholders

Shots without media become timeline blanks and are listed in the assembly guide.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: ComfyUI-native tutorial compiler](tutorials.md) · [Next: Security and path policy](security.md)
<!-- DOC_NAV_FOOTER_END -->
