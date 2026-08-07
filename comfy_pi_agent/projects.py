from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .docx_writer import write_docx
from .fountain import build_fountain
from .io_utils import atomic_write_json, atomic_write_text, resolve_output_root, safe_join, slugify

ALL_STAGES = [
    "01_intake", "02_project_brief", "03_creative_development", "04_writing",
    "05_screenplay", "06_bibles", "07_references", "08_scene_breakdown",
    "09_shot_planning", "10_storyboards", "11_prompt_generation",
    "12_workflow_generation", "13_media_generation", "14_quality_control",
    "15_editorial_preparation", "16_nle_packaging", "17_documentation",
    "18_completion_audit"
]

# The directory names are intentionally explicit. A user should be able to open a
# generated project and know where a file belongs without reading source code.
PROJECT_DIRECTORY_LAYOUT: list[dict[str, Any]] = [
    {
        "path": "00_PROJECT_ADMIN",
        "title": "Project Administration",
        "purpose": "Start here. This folder contains the project brief, assumptions, status, manifests, asset catalog, and directory map.",
        "subdirectories": [
            ("01_MANIFESTS", "Machine-readable project, production, workflow, and asset manifests."),
            ("02_STATUS_AND_REPORTS", "Project status, completion reports, warnings, and progress summaries."),
            ("03_NOTES_AND_DECISIONS", "Human notes, approvals, creative decisions, and change records."),
            ("04_IMPORT_INBOX", "New files that have not yet been sorted. Move them into their permanent labeled folder after review."),
        ],
    },
    {
        "path": "01_STORY",
        "title": "Story",
        "purpose": "All story development and prose writing belongs here, before or alongside the screenplay adaptation.",
        "subdirectories": [
            ("01_CONCEPT_LOGLINE_AND_PREMISE", "Concepts, loglines, premises, themes, and short project descriptions."),
            ("02_TREATMENTS_AND_SYNOPSIS", "Treatments, synopses, summaries, and pitch documents."),
            ("03_OUTLINES_BEATS_AND_CHAPTER_PLANS", "Story outlines, beat sheets, chapter plans, and scene outlines."),
            ("04_MANUSCRIPT", "The current story, novella, novel, or other prose manuscript."),
            ("05_REVISIONS_AND_ARCHIVED_DRAFTS", "Older story drafts and revision snapshots that should not be confused with the current manuscript."),
        ],
    },
    {
        "path": "02_SCREENPLAY",
        "title": "Screenplay",
        "purpose": "All screenplay files, adaptations, Fountain sources, readable exports, and screenplay revisions belong here.",
        "subdirectories": [
            ("01_FOUNTAIN", "Canonical .fountain screenplay files."),
            ("02_MARKDOWN", "Readable Markdown screenplay exports and notes."),
            ("03_DOCX", "Microsoft Word screenplay exports."),
            ("04_ADAPTATION_MAPS", "Maps showing how story chapters and scenes became screenplay scenes."),
            ("05_REVISIONS_AND_ARCHIVED_DRAFTS", "Older screenplay drafts and revisions."),
        ],
    },
    {
        "path": "03_PRODUCTION_BIBLES",
        "title": "Production Bibles",
        "purpose": "Approved project facts and continuity rules live here. These files are the long-term memory for the production.",
        "subdirectories": [
            ("01_STORY_BIBLE", "Story rules, themes, plot facts, setups, payoffs, and approved narrative information."),
            ("02_CHARACTER_BIBLE", "Character identities, arcs, relationships, behavior, and canonical descriptions."),
            ("03_WORLD_AND_LORE_BIBLE", "World rules, history, lore, technology, culture, and fictional systems."),
            ("04_LOCATION_AND_ENVIRONMENT_BIBLE", "Canonical locations, sets, environments, geography, and recurring scene details."),
            ("05_TIMELINE_AND_CONTINUITY_BIBLE", "Timeline, scene continuity, injuries, damage, weather, entrances, exits, and state changes."),
            ("06_WARDROBE_HAIR_AND_MAKEUP_BIBLE", "Wardrobe, hair, makeup, dirt, age variants, and scene-by-scene appearance continuity."),
            ("07_PROP_VEHICLE_AND_CREATURE_BIBLE", "Props, tools, vehicles, creatures, condition changes, and continuity rules."),
            ("08_VISUAL_STYLE_AND_COLOR_BIBLE", "Approved visual language, palettes, materials, typography, and style constraints."),
            ("09_CINEMATOGRAPHY_AND_LIGHTING_BIBLE", "Camera, lens, framing, movement, lighting, and composition rules."),
            ("10_VOICE_DIALOGUE_AND_PRONUNCIATION_BIBLE", "Voice identities, dialogue rules, pronunciation, accents, delivery, and consent metadata."),
            ("11_MUSIC_SOUND_AND_AUDIO_BIBLE", "Music themes, instrumentation, sound design, ambience, mix references, and audio rules."),
            ("12_WORKFLOW_MODEL_AND_TECHNICAL_BIBLE", "Approved models, model versions, GGUF or safetensors choices, node packs, workflows, and technical settings."),
        ],
    },
    {
        "path": "04_MOOD_BOARDS",
        "title": "Mood Boards",
        "purpose": "Mood boards and look-development collections are kept here as clearly labeled boards, source images, annotations, and approved versions.",
        "subdirectories": [
            ("01_PROJECT_LOOK_AND_TONE", "Overall project mood, tone, visual direction, and look development."),
            ("02_CHARACTER_MOOD_BOARDS", "Character-specific emotion, wardrobe, pose, material, and style direction."),
            ("03_LOCATION_AND_ENVIRONMENT_MOOD_BOARDS", "Locations, architecture, weather, environment, and atmosphere."),
            ("04_WARDROBE_PROP_AND_VEHICLE_MOOD_BOARDS", "Wardrobe, props, tools, products, and vehicles."),
            ("05_COLOR_LIGHTING_AND_CINEMATOGRAPHY_BOARDS", "Color scripts, lighting boards, framing, lenses, and camera inspiration."),
            ("06_MUSIC_AUDIO_AND_RHYTHM_BOARDS", "Music, rhythm, sound, ambience, and performance direction."),
            ("07_APPROVED_BOARDS", "Approved mood boards that may be used automatically by production workflows."),
            ("08_DRAFT_AND_REJECTED_BOARDS", "Drafts and rejected directions kept for history but not used automatically."),
        ],
    },
    {
        "path": "05_REFERENCE_SHEETS",
        "title": "Reference Sheets",
        "purpose": "Character sheets, turnarounds, expressions, poses, locations, props, voices, music, and other reusable references belong here.",
        "subdirectories": [
            ("01_CHARACTER_MASTER_SHEETS", "Canonical full character reference sheets and individual high-resolution panels."),
            ("02_CHARACTER_EXPRESSIONS", "Expression sheets and face close-ups."),
            ("03_CHARACTER_POSES_AND_TURNAROUNDS", "Pose sheets, scale sheets, front/profile/rear views, and turnarounds."),
            ("04_WARDROBE_HAIR_AND_MAKEUP", "Wardrobe variants, hair, makeup, dirt, injury, and age variants."),
            ("05_LOCATIONS_SETS_AND_ENVIRONMENTS", "Location, set, room, environment, and architecture reference sheets."),
            ("06_PROPS_TOOLS_VEHICLES_AND_PRODUCTS", "Prop, tool, vehicle, product, and material reference sheets."),
            ("07_CREATURES_ANIMALS_AND_PLANTS", "Creature, animal, plant, and organic reference sheets."),
            ("08_VOICE_REFERENCES", "Raw voice recordings, cleaned clips, transcripts, pronunciation guides, and model-specific voice data."),
            ("09_MUSIC_AUDIO_AND_SOUND_REFERENCES", "Music, instrument, rhythm, ambience, sound-effect, and mix references."),
            ("10_APPROVED_REFERENCES", "Approved references that may be selected automatically."),
            ("11_DRAFT_AND_REJECTED_REFERENCES", "Draft or rejected references kept for comparison and history."),
        ],
    },
    {
        "path": "06_STORYBOARDS",
        "title": "Storyboards",
        "purpose": "All storyboard panels and storyboard documents live here, separated by sequence, scene, shot, approval state, and animatic use.",
        "subdirectories": [
            ("01_SEQUENCE_BOARDS", "Boards covering complete sequences or major story sections."),
            ("02_SCENE_BOARDS", "Boards organized by screenplay scene."),
            ("03_SHOT_BOARDS", "Individual shot panels and technical shot boards."),
            ("04_ANIMATIC_ASSETS", "Panels, timing sheets, temporary dialogue, and audio prepared for animatics."),
            ("05_APPROVED_STORYBOARDS", "Approved storyboards used by downstream prompt and workflow generation."),
            ("06_DRAFT_AND_REJECTED_STORYBOARDS", "Draft and rejected boards kept for revision history."),
        ],
    },
    {
        "path": "07_SCENE_AND_SHOT_PLANS",
        "title": "Scene and Shot Plans",
        "purpose": "Screenplay breakdowns, scene lists, shot lists, blocking, coverage, and continuity plans belong here.",
        "subdirectories": [
            ("01_SCREENPLAY_BREAKDOWNS", "Scene-by-scene production breakdowns."),
            ("02_SCENE_LISTS", "Ordered scene lists, scene summaries, dependencies, and status."),
            ("03_SHOT_LISTS", "Shot IDs, framing, movement, action, timing, references, and workflow status."),
            ("04_CAMERA_BLOCKING_AND_COVERAGE", "Camera diagrams, blocking plans, screen direction, and alternate coverage."),
            ("05_CONTINUITY_TRACKING", "Shot entry/exit state, visual continuity, audio continuity, and continuity reports."),
        ],
    },
    {
        "path": "08_PROMPTS",
        "title": "Prompts",
        "purpose": "All production prompts are separated by media type so they can be found, reviewed, reused, and versioned quickly.",
        "subdirectories": [
            ("01_IMAGE_GENERATION", "Text-to-image prompts and settings."),
            ("02_IMAGE_EDITING", "Image-edit instructions, preservation prompts, masks, and reference roles."),
            ("03_VIDEO_GENERATION", "Text-to-video, image-to-video, reference-video, first-frame, and last-frame prompts."),
            ("04_VOICE_DIALOGUE_AND_NARRATION", "TTS, voice design, voice clone, dialogue, narration, and pronunciation prompts."),
            ("05_MUSIC_AND_SONGS", "Music, score, song, lyrics, arrangement, and ACE-Step prompts."),
            ("06_SOUND_EFFECTS_FOLEY_AND_AMBIENCE", "Sound-effect, foley, room-tone, ambience, and audio-edit prompts."),
            ("07_NEGATIVE_PRESERVATION_AND_CONTINUITY", "Negative prompts, do-not-change rules, preservation instructions, and continuity constraints."),
        ],
    },
    {
        "path": "09_COMFYUI_WORKFLOWS",
        "title": "ComfyUI Workflows",
        "purpose": "Every ComfyUI workflow is kept here and separated by status and format so the current validated workflow is easy to find.",
        "subdirectories": [
            ("01_ORIGINAL_WORKFLOWS", "Unmodified imported or generated source workflows."),
            ("02_VALIDATED_WORKFLOWS", "Workflows validated against the current ComfyUI node schemas."),
            ("03_REPAIRED_WORKFLOWS", "Repaired copies and their structured diffs."),
            ("04_API_WORKFLOWS", "API-format workflows used for headless or automated execution."),
            ("05_GGUF_WORKFLOW_VARIANTS", "Validated or clearly labeled experimental GGUF loader variants."),
            ("06_SAFETENSORS_WORKFLOW_VARIANTS", "Safetensors workflow variants."),
            ("07_TUTORIAL_WORKFLOWS", "Annotated tutorial copies, controller workflows, and overview workflows."),
            ("08_ARCHIVED_AND_SUPERSEDED_WORKFLOWS", "Old workflows that should not be used for current production."),
        ],
    },
    {
        "path": "10_GENERATED_MEDIA",
        "title": "Generated Media",
        "purpose": "Raw outputs from ComfyUI are stored here by media type. These are source outputs, not necessarily the final editorial copies.",
        "subdirectories": [
            ("01_IMAGES", "Generated images and still frames."),
            ("02_VIDEO", "Generated video clips."),
            ("03_DIALOGUE", "Generated character dialogue."),
            ("04_NARRATION", "Generated narration and voice-over."),
            ("05_MUSIC", "Generated songs, score, cues, and musical stems."),
            ("06_SOUND_EFFECTS_AND_FOLEY", "Generated sound effects and foley."),
            ("07_AMBIENCE_AND_ROOM_TONE", "Generated ambience, room tone, weather, and background sound."),
            ("08_TITLES_GRAPHICS_AND_SUBTITLES", "Generated titles, graphics, captions, subtitle files, and overlays."),
            ("09_FAILED_REJECTED_AND_TEST_OUTPUTS", "Failed, rejected, or temporary test outputs that must not be mistaken for approved media."),
        ],
    },
    {
        "path": "11_EDITORIAL_MEDIA",
        "title": "Editorial Media",
        "purpose": "NLE-ready copies are stored here after validation and normalization. Original generated files remain in 10_GENERATED_MEDIA.",
        "subdirectories": [
            ("01_VIDEO", "Editorial-ready video clips."),
            ("02_IMAGE_SEQUENCES", "Numbered image sequences prepared for editing."),
            ("03_DIALOGUE", "Editorial-ready dialogue."),
            ("04_NARRATION", "Editorial-ready narration and voice-over."),
            ("05_MUSIC", "Editorial-ready music and cues."),
            ("06_SOUND_EFFECTS_AND_FOLEY", "Editorial-ready sound effects and foley."),
            ("07_AMBIENCE_AND_ROOM_TONE", "Editorial-ready ambience and room tone."),
            ("08_AUDIO_STEMS", "Separated dialogue, music, effects, ambience, and other mix stems."),
            ("09_TITLES_GRAPHICS_AND_SUBTITLES", "Editorial-ready titles, graphics, captions, and subtitle files."),
            ("10_PROXIES", "Proxy media for smoother NLE playback."),
        ],
    },
    {
        "path": "12_NLE_PROJECT",
        "title": "NLE Project",
        "purpose": "Kdenlive is the default editor. Native projects, portable timeline files, media maps, and assembly guides are kept here.",
        "subdirectories": [
            ("01_KDENLIVE", "Kdenlive project files, project profiles, bin maps, timeline layouts, and titles."),
            ("02_OPENTIMELINEIO", "Portable OTIO timelines and related metadata."),
            ("03_EDL_CSV_AND_MEDIA_MAPS", "EDL, CSV, markers, checksums, and media-location maps."),
            ("04_OTHER_NLE_EXPORTS", "Files prepared for other supported NLE editors."),
            ("05_ASSEMBLY_GUIDES", "Plain-language instructions for opening, relinking, assembling, editing, rendering, and archiving the project."),
        ],
    },
    {
        "path": "13_TUTORIALS_AND_DOCUMENTATION",
        "title": "Tutorials and Documentation",
        "purpose": "Complete project tutorials, workflow tutorials, installation guides, troubleshooting, and exported documents belong here.",
        "subdirectories": [
            ("01_COMPLETE_PROJECT_TUTORIAL", "The complete ComfyUI-native tutorial for the full project."),
            ("02_WORKFLOW_TUTORIALS", "Tutorials for individual or grouped workflows."),
            ("03_INSTALLATION_AND_SETUP", "Installation, model placement, custom-node requirements, and setup instructions."),
            ("04_TROUBLESHOOTING_AND_REPAIR", "Known errors, diagnosis, repair instructions, and validation reports."),
            ("05_MARKDOWN_DOCX_AND_OTHER_EXPORTS", "Markdown, DOCX, Fountain, JSON, and other document exports."),
        ],
    },
    {
        "path": "14_QUALITY_CONTROL",
        "title": "Quality Control",
        "purpose": "Technical validation, continuity checks, approval reviews, missing-asset reports, and repair reports belong here.",
        "subdirectories": [
            ("01_TECHNICAL_VALIDATION", "File, codec, resolution, duration, workflow, and schema checks."),
            ("02_VISUAL_AND_CONTINUITY_REVIEW", "Character, wardrobe, prop, environment, camera, lighting, and shot continuity checks."),
            ("03_AUDIO_AND_DIALOGUE_REVIEW", "Voice, dialogue, pronunciation, loudness, music, effects, and audio continuity checks."),
            ("04_MISSING_ASSETS_AND_BLOCKERS", "Precise reports of missing models, nodes, references, files, and unfinished production items."),
            ("05_APPROVALS_REJECTIONS_AND_REPAIR_REPORTS", "Approval records, rejection reasons, diffs, and repair reports."),
        ],
    },
    {
        "path": "15_DELIVERY",
        "title": "Delivery",
        "purpose": "Final approved deliverables, completion reports, checksums, release notes, and distribution packages belong here.",
        "subdirectories": [
            ("01_FINAL_MASTERS", "Final master video, audio, images, and other approved outputs."),
            ("02_WEB_SOCIAL_AND_ALTERNATE_EXPORTS", "Platform-specific and alternate delivery versions."),
            ("03_PROJECT_COMPLETION_REPORTS", "Completion status, unresolved items, model records, and final audit documents."),
            ("04_CHECKSUMS_LICENSES_AND_RELEASE_NOTES", "Checksums, licenses, credits, attribution, rights records, and release notes."),
        ],
    },
    {
        "path": "16_ARCHIVE",
        "title": "Archive",
        "purpose": "Superseded, frozen, or long-term preservation packages belong here. Current working assets should remain in their labeled production folders.",
        "subdirectories": [
            ("01_PROJECT_SNAPSHOTS", "Versioned snapshots of the complete project state."),
            ("02_NLE_ARCHIVES", "Portable Kdenlive or other NLE archive packages."),
            ("03_SUPERSEDED_ASSETS", "Old assets retained for history but not used by current production."),
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _layout_paths() -> list[str]:
    paths: list[str] = []
    for section in PROJECT_DIRECTORY_LAYOUT:
        paths.append(section["path"])
        for subdirectory, _purpose in section["subdirectories"]:
            paths.append(f"{section['path']}/{subdirectory}")
    return paths


def create_project_plan(request: str, project_name: str = "", production_type: str = "auto", target_nle: str = "kdenlive") -> dict[str, Any]:
    name = project_name.strip() or request.strip().split("\n", 1)[0][:72] or "Untitled Project"
    lower = request.lower()
    narrative = any(word in lower for word in ("film", "movie", "story", "screenplay", "book", "episode", "scene"))
    audio = any(word in lower for word in ("music", "song", "voice", "dialogue", "audio", "sound"))
    tutorial = "tutorial" in lower
    stages = []
    for stage in ALL_STAGES:
        optional = False
        reason = "Required for a complete production."
        if stage in {"04_writing", "05_screenplay", "08_scene_breakdown", "09_shot_planning"} and not narrative:
            optional = True
            reason = "Created only when the project needs a narrative or planned shots."
        if stage == "10_storyboards" and not narrative:
            optional = True
            reason = "Storyboards are optional for small or non-narrative projects."
        if stage == "13_media_generation":
            reason = "Executes approved ComfyUI workflows when the user enables execution."
        if stage == "16_nle_packaging":
            reason = f"Creates the editorial handoff; the default target is {target_nle}."
        stages.append({"stage_id": stage, "optional": optional, "status": "planned", "reason": reason})
    artifacts = [
        "START_HERE.md",
        "PROJECT_DIRECTORY_GUIDE.md",
        "00_PROJECT_ADMIN/PROJECT_BRIEF.md",
        "00_PROJECT_ADMIN/01_MANIFESTS/production-manifest.json",
        "00_PROJECT_ADMIN/01_MANIFESTS/asset-catalog.json",
    ]
    if narrative:
        artifacts += [
            "01_STORY/03_OUTLINES_BEATS_AND_CHAPTER_PLANS/story-outline.md",
            "01_STORY/04_MANUSCRIPT/story.md",
            "02_SCREENPLAY/01_FOUNTAIN/screenplay.fountain",
            "07_SCENE_AND_SHOT_PLANS/02_SCENE_LISTS/scene-list.json",
            "07_SCENE_AND_SHOT_PLANS/03_SHOT_LISTS/shot-list.json",
            "06_STORYBOARDS/storyboard-manifest.json",
        ]
    if audio:
        artifacts += [
            "03_PRODUCTION_BIBLES/10_VOICE_DIALOGUE_AND_PRONUNCIATION_BIBLE/voice-bible.json",
            "03_PRODUCTION_BIBLES/11_MUSIC_SOUND_AND_AUDIO_BIBLE/music-audio-bible.json",
        ]
    if tutorial:
        artifacts += [
            "13_TUTORIALS_AND_DOCUMENTATION/01_COMPLETE_PROJECT_TUTORIAL/tutorial.json",
            "13_TUTORIALS_AND_DOCUMENTATION/01_COMPLETE_PROJECT_TUTORIAL/COMPLETE_TUTORIAL.md",
        ]
    return {
        "schema_version": "1.1",
        "project_id": slugify(name),
        "title": name,
        "request": request,
        "production_type": production_type,
        "target_nle": target_nle,
        "status": "planned",
        "created_at": utc_now(),
        "assumptions": {
            "resolution": "1920x1080",
            "frame_rate": "24/1",
            "audio_sample_rate": 48000,
            "screenplay_format": "Fountain",
            "documentation_formats": ["Markdown", "DOCX"],
            "path_policy": "project-relative paths preferred",
            "project_layout_version": "1.1-explicit-assets",
        },
        "capability_flags": {"narrative": narrative, "audio": audio, "tutorial": tutorial},
        "stages": stages,
        "planned_artifacts": artifacts,
        "project_directories": _layout_paths(),
        "warnings": [
            "Media generation requires compatible models and nodes installed in ComfyUI.",
            "Pi reasoning requires a configured Pi runtime and model provider."
        ]
    }


def _directory_readme(title: str, path: str, purpose: str, children: list[tuple[str, str]] | None = None) -> str:
    text = [
        f"# {title}",
        "",
        f"**Project path:** `{path}`",
        "",
        purpose,
        "",
        "## File rule",
        "",
        "Put files here only when they match this folder's purpose. Keep current approved files clearly named and move older or rejected versions into the labeled draft, rejected, revision, or archive folder.",
    ]
    if children:
        text += ["", "## Subdirectories", ""]
        for child, child_purpose in children:
            text.append(f"- **`{child}/`** — {child_purpose}")
    text += ["", "## Naming guidance", "", "Use stable names that include the project, scene or character when useful, the asset role, and a version number. Example: `Project_SC012_SH003_character-reference_v002.png`.", ""]
    return "\n".join(text)


def _make_dirs(root: Path) -> list[str]:
    created: list[str] = []
    for section in PROJECT_DIRECTORY_LAYOUT:
        top = safe_join(root, section["path"])
        top.mkdir(parents=True, exist_ok=True)
        atomic_write_text(top / "README.md", _directory_readme(section["title"], section["path"], section["purpose"], section["subdirectories"]))
        created.append(section["path"])
        for subdirectory, purpose in section["subdirectories"]:
            child = safe_join(top, subdirectory)
            child.mkdir(parents=True, exist_ok=True)
            child_title = subdirectory.replace("_", " ").title()
            atomic_write_text(child / "README.md", _directory_readme(child_title, f"{section['path']}/{subdirectory}", purpose))
            created.append(f"{section['path']}/{subdirectory}")
    return created


def _project_directory_guide(title: str) -> str:
    lines = [
        f"# {title} — Project Directory Guide",
        "",
        "This project uses explicit numbered folders. You should not need to guess where an asset belongs.",
        "",
        "## Fast file-location guide",
        "",
        "- Story, outline, treatment, or manuscript → `01_STORY/`",
        "- Fountain screenplay or screenplay export → `02_SCREENPLAY/`",
        "- Character, world, continuity, voice, music, or workflow bible → `03_PRODUCTION_BIBLES/`",
        "- Mood board, look board, lighting board, or color board → `04_MOOD_BOARDS/`",
        "- Character sheet, turnaround, voice reference, location sheet, prop sheet, or music reference → `05_REFERENCE_SHEETS/`",
        "- Storyboard panels or animatic assets → `06_STORYBOARDS/`",
        "- Scene breakdown, scene list, shot list, camera plan, or continuity plan → `07_SCENE_AND_SHOT_PLANS/`",
        "- Image, video, voice, music, or sound prompt → `08_PROMPTS/`",
        "- ComfyUI workflow JSON → `09_COMFYUI_WORKFLOWS/`",
        "- Raw ComfyUI output → `10_GENERATED_MEDIA/`",
        "- NLE-ready normalized media → `11_EDITORIAL_MEDIA/`",
        "- Kdenlive, OTIO, EDL, media map, or assembly guide → `12_NLE_PROJECT/`",
        "- Complete tutorials and readable documentation → `13_TUTORIALS_AND_DOCUMENTATION/`",
        "- Validation, continuity, approval, or missing-asset report → `14_QUALITY_CONTROL/`",
        "- Final master or delivery package → `15_DELIVERY/`",
        "- Frozen snapshots and old project archives → `16_ARCHIVE/`",
        "",
        "## Complete top-level map",
        "",
    ]
    for section in PROJECT_DIRECTORY_LAYOUT:
        lines.append(f"### `{section['path']}/` — {section['title']}")
        lines.append("")
        lines.append(section["purpose"])
        lines.append("")
        for child, purpose in section["subdirectories"]:
            lines.append(f"- **`{child}/`** — {purpose}")
        lines.append("")
    return "\n".join(lines)


def compile_project(request: str, project_name: str = "", output_directory: str = "", production_type: str = "auto", target_nle: str = "kdenlive") -> dict[str, Any]:
    plan = create_project_plan(request, project_name, production_type, target_nle)
    base = resolve_output_root(output_directory, "projects")
    root = safe_join(base, plan["project_id"])
    root.mkdir(parents=True, exist_ok=True)
    created_directories = _make_dirs(root)

    start_here = f"""# START HERE — {plan['title']}

This is the main entry point for the project.

## What to open first

1. Read `PROJECT_DIRECTORY_GUIDE.md` to learn where every file belongs.
2. Read `00_PROJECT_ADMIN/PROJECT_BRIEF.md` for the original request and purpose.
3. Check `00_PROJECT_ADMIN/02_STATUS_AND_REPORTS/PROJECT_STATUS.md` before generating or editing assets.
4. Put unsorted imported files in `00_PROJECT_ADMIN/04_IMPORT_INBOX/`, then move them into the correct permanent folder.

## Most-used folders

- Story: `01_STORY/`
- Screenplay: `02_SCREENPLAY/`
- Production bibles: `03_PRODUCTION_BIBLES/`
- Mood boards: `04_MOOD_BOARDS/`
- Reference sheets: `05_REFERENCE_SHEETS/`
- Storyboards: `06_STORYBOARDS/`
- Scene and shot plans: `07_SCENE_AND_SHOT_PLANS/`
- Prompts: `08_PROMPTS/`
- ComfyUI workflows: `09_COMFYUI_WORKFLOWS/`
- Generated media: `10_GENERATED_MEDIA/`
- Editorial media: `11_EDITORIAL_MEDIA/`
- Kdenlive and NLE files: `12_NLE_PROJECT/`
- Tutorials and documents: `13_TUTORIALS_AND_DOCUMENTATION/`

## Status

This new project is **planned**, not finished. The folder structure and starter files exist. Media becomes complete only after required workflows run, assets pass validation, and the completion audit has no blocking item.
"""
    atomic_write_text(root / "START_HERE.md", start_here)
    guide_text = _project_directory_guide(plan["title"])
    atomic_write_text(root / "PROJECT_DIRECTORY_GUIDE.md", guide_text)
    write_docx(root / "PROJECT_DIRECTORY_GUIDE.docx", guide_text, "Project Directory Guide")

    brief = f"""# {plan['title']}

## Original request

{request}

## Purpose

This project was created by ComfyUI Pi Agent. Every major production asset has its own plainly labeled directory so story files, screenplays, mood boards, reference sheets, storyboards, prompts, workflows, media, and NLE files are easy to find.

## Current status

**Planned.** The project structure and starting documents exist. Media is not called complete until every required workflow has run and the completion audit has no blocking item.
"""
    assumptions = "# Project Assumptions\n\n" + "\n".join(f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in plan["assumptions"].items()) + "\n"
    status = "# Project Status\n\n- Status: planned\n- Blocking items: models, references, workflows, and generated media must be checked before production.\n"
    atomic_write_text(safe_join(root, "00_PROJECT_ADMIN", "PROJECT_BRIEF.md"), brief)
    write_docx(safe_join(root, "00_PROJECT_ADMIN", "PROJECT_BRIEF.docx"), brief, plan["title"])
    atomic_write_text(safe_join(root, "00_PROJECT_ADMIN", "PROJECT_ASSUMPTIONS.md"), assumptions)
    atomic_write_text(safe_join(root, "00_PROJECT_ADMIN", "02_STATUS_AND_REPORTS", "PROJECT_STATUS.md"), status)
    atomic_write_json(safe_join(root, "00_PROJECT_ADMIN", "01_MANIFESTS", "project.json"), plan)

    manifest = {
        "schema_version": "1.1",
        "project_id": plan["project_id"],
        "title": plan["title"],
        "status": "planned",
        "target_nle": target_nle,
        "profile": plan["assumptions"],
        "directory_layout": created_directories,
        "sequences": [], "scenes": [], "shots": [], "references": [], "prompts": [],
        "workflows": [], "assets": [], "editorial": {}, "quality_control": {},
        "missing_requirements": ["Run model and custom-node preflight", "Create or import production workflows"]
    }
    atomic_write_json(safe_join(root, "00_PROJECT_ADMIN", "01_MANIFESTS", "production-manifest.json"), manifest)
    asset_catalog = {
        "schema_version": "1.1",
        "project_id": plan["project_id"],
        "instructions": "Register assets here with their permanent project-relative path. Do not leave approved assets in the import inbox.",
        "asset_roots": {
            "stories": "01_STORY",
            "screenplays": "02_SCREENPLAY",
            "bibles": "03_PRODUCTION_BIBLES",
            "mood_boards": "04_MOOD_BOARDS",
            "reference_sheets": "05_REFERENCE_SHEETS",
            "storyboards": "06_STORYBOARDS",
            "scene_and_shot_plans": "07_SCENE_AND_SHOT_PLANS",
            "prompts": "08_PROMPTS",
            "workflows": "09_COMFYUI_WORKFLOWS",
            "generated_media": "10_GENERATED_MEDIA",
            "editorial_media": "11_EDITORIAL_MEDIA",
            "nle_projects": "12_NLE_PROJECT",
            "tutorials_and_docs": "13_TUTORIALS_AND_DOCUMENTATION",
            "quality_control": "14_QUALITY_CONTROL",
            "delivery": "15_DELIVERY",
        },
        "assets": []
    }
    atomic_write_json(safe_join(root, "00_PROJECT_ADMIN", "01_MANIFESTS", "asset-catalog.json"), asset_catalog)
    atomic_write_json(safe_join(root, "00_PROJECT_ADMIN", "01_MANIFESTS", "directory-map.json"), {"schema_version": "1.1", "directories": PROJECT_DIRECTORY_LAYOUT})

    if plan["capability_flags"]["narrative"]:
        story_outline = f"# {plan['title']} — Story Outline\n\n## Original project request\n\n{request}\n\n## Outline status\n\nDraft. Develop the premise, characters, beats, chapters, or scenes here before treating it as approved.\n"
        manuscript = f"# {plan['title']} — Story Manuscript\n\nThis is the clearly labeled manuscript location. Replace this starter text with the current approved story or book draft.\n"
        atomic_write_text(safe_join(root, "01_STORY", "03_OUTLINES_BEATS_AND_CHAPTER_PLANS", "story-outline.md"), story_outline)
        atomic_write_text(safe_join(root, "01_STORY", "04_MANUSCRIPT", "story.md"), manuscript)
        fountain = build_fountain(plan["title"], "", request, "UNSPECIFIED LOCATION")
        atomic_write_text(safe_join(root, "02_SCREENPLAY", "01_FOUNTAIN", "screenplay.fountain"), fountain)
        atomic_write_text(safe_join(root, "02_SCREENPLAY", "02_MARKDOWN", "screenplay-notes.md"), "# Screenplay Notes\n\nThe Fountain screenplay is the canonical screenplay source. Keep adaptation and revision notes here.\n")
        atomic_write_json(safe_join(root, "07_SCENE_AND_SHOT_PLANS", "02_SCENE_LISTS", "scene-list.json"), {"schema_version": "1.0", "status": "draft", "scenes": []})
        atomic_write_json(safe_join(root, "07_SCENE_AND_SHOT_PLANS", "03_SHOT_LISTS", "shot-list.json"), {"schema_version": "1.0", "status": "draft", "shots": []})
        atomic_write_json(safe_join(root, "06_STORYBOARDS", "storyboard-manifest.json"), {"schema_version": "1.0", "status": "draft", "sequences": [], "scenes": [], "shots": []})

    bible_targets = {
        "story-bible.json": "03_PRODUCTION_BIBLES/01_STORY_BIBLE",
        "character-bible.json": "03_PRODUCTION_BIBLES/02_CHARACTER_BIBLE",
        "world-lore-bible.json": "03_PRODUCTION_BIBLES/03_WORLD_AND_LORE_BIBLE",
        "location-environment-bible.json": "03_PRODUCTION_BIBLES/04_LOCATION_AND_ENVIRONMENT_BIBLE",
        "timeline-continuity-bible.json": "03_PRODUCTION_BIBLES/05_TIMELINE_AND_CONTINUITY_BIBLE",
        "wardrobe-hair-makeup-bible.json": "03_PRODUCTION_BIBLES/06_WARDROBE_HAIR_AND_MAKEUP_BIBLE",
        "prop-vehicle-creature-bible.json": "03_PRODUCTION_BIBLES/07_PROP_VEHICLE_AND_CREATURE_BIBLE",
        "visual-style-color-bible.json": "03_PRODUCTION_BIBLES/08_VISUAL_STYLE_AND_COLOR_BIBLE",
        "cinematography-lighting-bible.json": "03_PRODUCTION_BIBLES/09_CINEMATOGRAPHY_AND_LIGHTING_BIBLE",
        "voice-dialogue-pronunciation-bible.json": "03_PRODUCTION_BIBLES/10_VOICE_DIALOGUE_AND_PRONUNCIATION_BIBLE",
        "music-sound-audio-bible.json": "03_PRODUCTION_BIBLES/11_MUSIC_SOUND_AND_AUDIO_BIBLE",
        "workflow-model-technical-bible.json": "03_PRODUCTION_BIBLES/12_WORKFLOW_MODEL_AND_TECHNICAL_BIBLE",
    }
    for filename, directory in bible_targets.items():
        atomic_write_json(safe_join(root, directory, filename), {"schema_version": "1.0", "type": filename.removesuffix(".json").replace("-", "_"), "status": "draft", "entries": []})

    atomic_write_json(safe_join(root, "04_MOOD_BOARDS", "mood-board-manifest.json"), {"schema_version": "1.0", "status": "draft", "boards": []})
    atomic_write_json(safe_join(root, "05_REFERENCE_SHEETS", "reference-sheet-manifest.json"), {"schema_version": "1.0", "status": "draft", "references": []})
    atomic_write_json(safe_join(root, "08_PROMPTS", "prompt-manifest.json"), {"schema_version": "1.0", "status": "draft", "prompts": []})
    atomic_write_json(safe_join(root, "09_COMFYUI_WORKFLOWS", "workflow-manifest.json"), {"schema_version": "1.0", "status": "draft", "workflows": []})

    nle_guide = f"""# Assemble {plan['title']} in Kdenlive

This guide is stored in the clearly labeled NLE directory. It will be expanded when the timeline is compiled.

1. Keep the project folder structure unchanged.
2. Put final NLE-ready copies in `11_EDITORIAL_MEDIA/`.
3. Build the Kdenlive package with the **Pi Kdenlive Package** node.
4. Open files from `12_NLE_PROJECT/01_KDENLIVE/` or import the OTIO fallback from `12_NLE_PROJECT/02_OPENTIMELINEIO/`.
5. Replace every placeholder before the final render.
"""
    assembly_dir = safe_join(root, "12_NLE_PROJECT", "05_ASSEMBLY_GUIDES")
    atomic_write_text(assembly_dir / "ASSEMBLE_IN_KDENLIVE.md", nle_guide)
    write_docx(assembly_dir / "ASSEMBLE_IN_KDENLIVE.docx", nle_guide, "Assemble in Kdenlive")

    report = "# Project Completion Report\n\nStatus: **PLANNED**\n\nThe project structure is complete, but media generation and editorial validation have not yet been performed.\n"
    report_dir = safe_join(root, "15_DELIVERY", "03_PROJECT_COMPLETION_REPORTS")
    atomic_write_text(report_dir / "PROJECT_COMPLETION_REPORT.md", report)
    write_docx(report_dir / "PROJECT_COMPLETION_REPORT.docx", report, "Project Completion Report")

    return {
        "project_root": str(root),
        "plan": plan,
        "manifest": manifest,
        "asset_catalog": asset_catalog,
        "directory_layout": PROJECT_DIRECTORY_LAYOUT,
        "created": True,
    }


def create_reference_asset(reference_type: str, title: str, description: str, roles: str = "", source_files: str = "") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "reference_id": f"ref-{slugify(reference_type)}-{slugify(title)}",
        "reference_type": reference_type,
        "title": title,
        "version": 1,
        "status": "draft",
        "descriptions": [description] if description else [],
        "roles": [r.strip() for r in roles.split(",") if r.strip()],
        "files": [r.strip() for r in source_files.splitlines() if r.strip()],
        "identity_features": [], "style_features": [], "preservation_rules": [],
        "usage_rules": [], "negative_constraints": [], "model_hints": [],
        "provenance": {"source": "user_or_plugin", "created_at": utc_now()},
        "rights": {"status": "unknown", "allowed_uses": [], "prohibited_uses": []}
    }


def create_skill(project_directory: str, name: str, description: str, instructions: str) -> dict[str, Any]:
    root = resolve_output_root(project_directory, "skills")
    skill_dir = safe_join(root, slugify(name))
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = f"# {name}\n\n## Purpose\n\n{description}\n\n## Instructions\n\n{instructions}\n\n## Safety\n\n- Use live ComfyUI node schemas.\n- Do not invent model filenames.\n- Preserve originals before repair.\n- Do not hardcode personal paths.\n"
    atomic_write_text(skill_dir / "SKILL.md", skill_md)
    manifest = {"name": name, "description": description, "status": "draft", "entrypoint": "SKILL.md"}
    atomic_write_json(skill_dir / "skill.json", manifest)
    return {"skill_directory": str(skill_dir), "manifest": manifest}
