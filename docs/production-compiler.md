# Complete and incremental production compiler

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Stories, books, Fountain, and screenplays](writing-screenplay.md) · [Next: ComfyUI-native tutorial compiler](tutorials.md)
<!-- DOC_NAV_END -->


## Independent or whole-project use

Every node can run independently. The project compiler can also create a complete structure from one prompt.

## Stages

The standard production plan contains intake, brief, creative development, writing, screenplay, bibles, references, scene breakdown, shot planning, storyboards, prompts, workflows, media, quality control, editorial preparation, NLE packaging, documentation, and completion audit.


## Explicit project directories

The compiler does not hide important assets inside a generic writing, references, or production folder. It creates top-level directories named `01_STORY`, `02_SCREENPLAY`, `04_MOOD_BOARDS`, `05_REFERENCE_SHEETS`, `06_STORYBOARDS`, `07_SCENE_AND_SHOT_PLANS`, `08_PROMPTS`, and `09_COMFYUI_WORKFLOWS`.

Every folder and subfolder contains a `README.md`. The project root includes `START_HERE.md`, `PROJECT_DIRECTORY_GUIDE.md`, and a DOCX copy of the directory guide. See [Project directory layout](project-directory-layout.md).

The project administration directory also contains:

- `asset-catalog.json`, which maps asset categories to permanent project-relative locations;
- `directory-map.json`, which describes every generated directory;
- an import inbox for files that have not yet been sorted.

Approved files should not remain in the import inbox.

## Status honesty

Creating folders and plans is not the same as generating final media. Version 0.1.1 labels new projects `planned` and writes missing requirements into the manifest.

## Output path

An empty output path uses the ComfyUI user directory. An explicit path is accepted as a deliberate user choice. Child files are prevented from escaping the chosen root.

## Future incremental compilation

The manifest schema includes stable project, scene, shot, reference, workflow, and asset lists so later releases can invalidate and rebuild only affected downstream artifacts.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Stories, books, Fountain, and screenplays](writing-screenplay.md) · [Next: ComfyUI-native tutorial compiler](tutorials.md)
<!-- DOC_NAV_FOOTER_END -->
