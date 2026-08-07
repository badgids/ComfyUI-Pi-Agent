from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .io_utils import load_json, slugify
from .models import load_profiles


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _references(value: str | list | dict | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    parsed = load_json(value, default=[]) if isinstance(value, str) else value
    if isinstance(parsed, dict):
        if "references" in parsed and isinstance(parsed["references"], list):
            return parsed["references"]
        return [parsed]
    return parsed if isinstance(parsed, list) else []


def create_image_workflow_plan(request: str, model_family: str, mode: str, references: str | list | dict = "[]", preferred_format: str = "auto", speed: str = "balanced", quality: str = "balanced") -> dict[str, Any]:
    profiles = load_profiles()
    profile = profiles.get(model_family, {})
    refs = _references(references)
    steps = [
        "Inspect the running ComfyUI node registry and official installed templates.",
        "Resolve the exact model family, revision, variant, and component roles.",
        "Resolve safetensors or a validated GGUF component set.",
        "Assign an explicit role to every reference image.",
        "Create a model-specific prompt package.",
        "Build the loader and conditioning subgraph from live node schemas.",
        "Apply only validated acceleration, LoRA, and attention profiles.",
        "Validate every connection and required input before execution.",
        "Preserve the source workflow and return a diff for edits."
    ]
    required = list(profile.get("components", []))
    warnings = []
    if mode in {"image_edit", "inpaint", "outpaint", "multi_reference"} and not refs:
        warnings.append("This edit mode normally requires at least one source or reference image.")
    if preferred_format == "gguf":
        warnings.append("GGUF is selected as a preference. Loader, encoder, VAE/projector, and LoRA compatibility must still be validated component by component.")
    return {
        "schema_version": "1.0", "plan_id": f"image-{slugify(model_family)}-{slugify(mode)}",
        "created_at": _now(), "request": request, "modality": "image", "mode": mode,
        "model_family": model_family, "model_profile": profile, "preferred_format": preferred_format,
        "speed_preference": speed, "quality_preference": quality, "references": refs,
        "required_components": required, "workflow_steps": steps, "warnings": warnings,
        "status": "planned"
    }


def create_audio_workflow_plan(request: str, model_family: str, mode: str, reference_audio: str = "", duration: float = 30.0, language: str = "en", preferred_format: str = "auto") -> dict[str, Any]:
    profiles = load_profiles()
    profile = profiles.get(model_family, {})
    steps = [
        "Identify whether the request is speech, music, ambience, sound effect, or audio editing.",
        "Resolve model variant and required codec, autoencoder, text encoder, or language-model planner.",
        "Inspect live ComfyUI schemas or a validated sidecar adapter.",
        "Prepare reference audio without overwriting the original.",
        "Create model-specific prompt, lyrics, voice, timing, and metadata inputs.",
        "Build and validate the workflow before execution.",
        "Save full mix and useful stems separately for editorial use."
    ]
    warnings = []
    if mode in {"voice_clone", "cover", "repaint", "audio_to_audio", "continue"} and not reference_audio.strip():
        warnings.append("The selected mode normally requires a reference or source audio file.")
    return {
        "schema_version": "1.0", "plan_id": f"audio-{slugify(model_family)}-{slugify(mode)}",
        "created_at": _now(), "request": request, "modality": "audio", "mode": mode,
        "model_family": model_family, "model_profile": profile, "preferred_format": preferred_format,
        "reference_audio": reference_audio, "duration_seconds": duration, "language": language,
        "required_components": list(profile.get("components", [])), "workflow_steps": steps,
        "warnings": warnings, "status": "planned"
    }


def create_character_sheet_plan(description: str, views: str, expressions: str, wardrobe: str, model_family: str) -> dict[str, Any]:
    view_list = [v.strip() for v in views.split(",") if v.strip()]
    expression_list = [v.strip() for v in expressions.split(",") if v.strip()]
    wardrobe_list = [v.strip() for v in wardrobe.split(",") if v.strip()]
    return {
        "schema_version": "1.0", "type": "character_reference_plan", "created_at": _now(),
        "canonical_description": description, "model_family": model_family,
        "views": view_list or ["front", "three-quarter front", "profile", "rear"],
        "expressions": expression_list, "wardrobe_variants": wardrobe_list,
        "required_outputs": ["individual high-resolution panels", "combined reference sheet", "character profile JSON"],
        "preservation_rules": ["identity", "proportions", "distinctive marks", "canonical palette"],
        "workflow_steps": [
            "Separate canonical identity from pose, lighting, wardrobe, and background.",
            "Generate or edit each view using approved identity references.",
            "Evaluate consistency across panels.",
            "Repair only inconsistent panels.",
            "Keep individual panels and the combined sheet."
        ],
        "status": "planned"
    }


def create_moodboard_plan(title: str, direction: str, categories: str, source_references: str = "[]") -> dict[str, Any]:
    refs = _references(source_references)
    cats = [c.strip() for c in categories.split(",") if c.strip()]
    return {
        "schema_version": "1.0", "reference_type": "moodboard", "title": title,
        "status": "draft", "created_at": _now(), "direction": direction,
        "categories": cats or ["color", "lighting", "composition", "materials", "atmosphere"],
        "items": [{**r, "role": r.get("role", "unassigned")} if isinstance(r, dict) else {"source": str(r), "role": "unassigned"} for r in refs],
        "outputs": ["board image", "source image collection", "palette", "prompt-ready style summary", "JSON manifest"],
        "rules": ["Every item must have a role.", "Original source images remain separate.", "Alternate visual directions use separate versions."]
    }


def create_storyboard_plan(shot_list_value: str | dict, style_reference: str = "", detail_level: str = "detailed") -> dict[str, Any]:
    shot_list = load_json(shot_list_value, default={}) if isinstance(shot_list_value, str) else shot_list_value
    shots = shot_list.get("shots", []) if isinstance(shot_list, dict) else []
    panels = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        panels.append({
            "panel_id": f"panel-{shot.get('shot_id', len(panels)+1)}",
            "shot_id": shot.get("shot_id"), "scene_id": shot.get("scene_id"),
            "shot_size": shot.get("shot_size"), "camera_movement": shot.get("camera_movement"),
            "action": shot.get("action"), "characters": shot.get("subject"),
            "style_reference": style_reference, "status": "planned"
        })
    return {
        "schema_version": "1.0", "type": "storyboard_plan", "created_at": _now(),
        "detail_level": detail_level, "panels": panels,
        "workflow_steps": [
            "Load approved character, location, prop, wardrobe, and visual references.",
            "Generate one panel per shot with stable shot identifiers.",
            "Check screen direction, staging, and continuity.",
            "Regenerate selected panels without replacing approved panels.",
            "Export individual panels, sequence boards, and shot metadata."
        ]
    }


def create_bible(bible_type: str, title: str, source_text: str = "", entries_value: str = "[]") -> dict[str, Any]:
    entries = load_json(entries_value, default=[])
    if not isinstance(entries, list):
        entries = [entries]
    return {
        "schema_version": "1.0", "bible_id": f"{slugify(bible_type)}-{slugify(title)}",
        "bible_type": bible_type, "title": title, "status": "draft", "created_at": _now(),
        "source_text": source_text, "entries": entries,
        "rules": ["Inferred facts remain draft until reviewed.", "Approved entries are preferred for production.", "Locked entries are not silently changed."]
    }


def create_build_plan(project_value: str | dict, compile_mode: str, compile_target: str, scope_type: str, scope_ids: str) -> dict[str, Any]:
    project = load_json(project_value, default={}) if isinstance(project_value, str) else project_value
    stages = project.get("stages") or project.get("plan", {}).get("stages") or [] if isinstance(project, dict) else []
    ids = [v.strip() for v in scope_ids.split(",") if v.strip()]
    actions = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        status = stage.get("status", "planned")
        action = "preserve" if status in {"approved", "locked", "completed"} and compile_mode == "incremental" else "build"
        actions.append({"stage": stage.get("stage_id"), "action": action, "current_status": status, "reason": "Selected by compile target and project state."})
    return {
        "schema_version": "1.0", "type": "production_build_plan", "created_at": _now(),
        "compile_mode": compile_mode, "compile_target": compile_target,
        "scope": {"type": scope_type, "ids": ids}, "actions": actions,
        "preserve_approved": True, "preserve_locked": True,
        "warnings": ["This node creates the dependency-aware build plan. Execute media stages only after workflow and resource validation."]
    }
