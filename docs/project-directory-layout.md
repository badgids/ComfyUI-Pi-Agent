# Project directory layout

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Preemptive context handoff](context-handoff.md) · [Next: References, mood boards, storyboards, and bibles](references-bibles.md)
<!-- DOC_NAV_END -->


The project compiler creates a clearly labeled production workspace. Major assets are not hidden inside broad or vague folders.

Every generated project begins with:

```text
START_HERE.md
PROJECT_DIRECTORY_GUIDE.md
PROJECT_DIRECTORY_GUIDE.docx
```

Read `START_HERE.md` first. It points to the most important files and explains the project status. `PROJECT_DIRECTORY_GUIDE.md` explains every folder and subfolder.

## Fast file-location guide

| Asset | Project directory |
|---|---|
| Story, treatment, outline, or manuscript | `01_STORY/` |
| Fountain screenplay or screenplay export | `02_SCREENPLAY/` |
| Character, world, continuity, visual, voice, music, or workflow bible | `03_PRODUCTION_BIBLES/` |
| Mood board, lighting board, color board, or look-development board | `04_MOOD_BOARDS/` |
| Character sheet, turnaround, pose sheet, location sheet, voice reference, or audio reference | `05_REFERENCE_SHEETS/` |
| Storyboard panels or animatic assets | `06_STORYBOARDS/` |
| Scene breakdown, scene list, shot list, blocking, or continuity plan | `07_SCENE_AND_SHOT_PLANS/` |
| Image, video, voice, music, or sound prompt | `08_PROMPTS/` |
| ComfyUI workflow JSON | `09_COMFYUI_WORKFLOWS/` |
| Raw ComfyUI output | `10_GENERATED_MEDIA/` |
| NLE-ready normalized media | `11_EDITORIAL_MEDIA/` |
| Kdenlive, OTIO, EDL, media map, or assembly guide | `12_NLE_PROJECT/` |
| Complete tutorial or other readable documentation | `13_TUTORIALS_AND_DOCUMENTATION/` |
| Validation, continuity, missing-asset, approval, or repair report | `14_QUALITY_CONTROL/` |
| Final master or delivery package | `15_DELIVERY/` |
| Frozen snapshots and old project archives | `16_ARCHIVE/` |

## Complete top-level layout

```text
Project_Name/
├── START_HERE.md
├── PROJECT_DIRECTORY_GUIDE.md
├── PROJECT_DIRECTORY_GUIDE.docx
├── 00_PROJECT_ADMIN/
├── 01_STORY/
├── 02_SCREENPLAY/
├── 03_PRODUCTION_BIBLES/
├── 04_MOOD_BOARDS/
├── 05_REFERENCE_SHEETS/
├── 06_STORYBOARDS/
├── 07_SCENE_AND_SHOT_PLANS/
├── 08_PROMPTS/
├── 09_COMFYUI_WORKFLOWS/
├── 10_GENERATED_MEDIA/
├── 11_EDITORIAL_MEDIA/
├── 12_NLE_PROJECT/
├── 13_TUTORIALS_AND_DOCUMENTATION/
├── 14_QUALITY_CONTROL/
├── 15_DELIVERY/
└── 16_ARCHIVE/
```

## Folder labels

Every top-level folder and every generated subfolder contains a `README.md` that explains:

- what belongs in the folder;
- what does not belong there;
- how files should be named;
- which child folders are available.

This means a user can open any directory and immediately understand its purpose.

## Project administration and asset catalog

`00_PROJECT_ADMIN/01_MANIFESTS/asset-catalog.json` maps each asset category to its permanent project directory. The production compiler and later automation should store project-relative paths in this catalog.

`00_PROJECT_ADMIN/04_IMPORT_INBOX/` is the only temporary unsorted location. Imported files may be placed there before review, but approved production assets should be moved to their permanent labeled directory.

## Story and screenplay separation

Story prose and screenplay files are separate because they serve different jobs:

- `01_STORY/` contains concepts, treatments, outlines, beat sheets, chapters, and manuscripts.
- `02_SCREENPLAY/` contains the canonical Fountain screenplay, readable exports, adaptation maps, and screenplay revisions.

The plugin should never make users search through a general `writing` folder to find the current story or screenplay.

## Mood boards, reference sheets, and storyboards

These are separate top-level asset classes:

- `04_MOOD_BOARDS/` controls visual and audio direction.
- `05_REFERENCE_SHEETS/` stores reusable identity, appearance, environment, prop, voice, music, and sound references.
- `06_STORYBOARDS/` stores sequence, scene, and shot boards plus animatic assets.

Approved and draft/rejected material have separate labeled subdirectories to prevent accidental use of an old or rejected reference.

## Prompts and workflows

Prompts and workflows are also separate:

- `08_PROMPTS/` organizes prompts by image, image edit, video, voice, music, sound, and preservation rules.
- `09_COMFYUI_WORKFLOWS/` separates original, validated, repaired, API, GGUF, safetensors, tutorial, and archived workflows.

This makes the current validated workflow easy to locate.

## Generated media versus editorial media

The project keeps source outputs and NLE-ready copies separate:

- `10_GENERATED_MEDIA/` contains raw outputs from ComfyUI.
- `11_EDITORIAL_MEDIA/` contains validated or normalized copies prepared for Kdenlive or another NLE.

The plugin must preserve original generated media when it creates editorial copies.

## Naming guidance

Use stable names that identify the project, scene, shot, character or asset role, and version when useful.

Examples:

```text
Pippa_SC012_SH003_storyboard_v002.png
Pippa_character-Pippa_turnaround_v004.png
Pippa_SC012_SH003_video_TK02_v003.mp4
Pippa_SC012_dialogue-Pippa_v002.wav
Pippa_screenplay_v006.fountain
```

Do not reuse the same filename for unrelated versions. Do not keep approved files in a folder labeled draft, rejected, failed, or archived.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Preemptive context handoff](context-handoff.md) · [Next: References, mood boards, storyboards, and bibles](references-bibles.md)
<!-- DOC_NAV_FOOTER_END -->
