from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .docx_writer import write_docx
from .fountain import build_fountain, create_shot_list, parse_fountain, screenplay_breakdown, validate_fountain
from .io_utils import atomic_write_json, atomic_write_text, json_text, load_json, resolve_output_root, safe_join, slugify
from .models import inventory_models, load_profiles, resolve_model
from .media_plans import (
    create_audio_workflow_plan, create_bible, create_build_plan,
    create_character_sheet_plan, create_image_workflow_plan,
    create_moodboard_plan, create_storyboard_plan,
)
from .nle import create_kdenlive_package
from .pi_runtime import discover_pi, run_pi_prompt
from .projects import compile_project, create_project_plan, create_reference_asset, create_skill
from .tutorials import compile_tutorial, load_tutorial, select_stage, tutorial_preflight, validate_stage
from .version import __version__
from .workflow import analyze_workflow, repair_workflow, validate_workflow
from .workflow_guard import finalize_generated_workflow, finalize_workflow_result
from importlib import import_module
from .integrations.router import build_dynamic_integration_context, integration_status
from .agent_guidance import build_request_guidance


def _minimax_h3():
    return import_module(".integrations.minimax_h3_director", package=__package__)


def _whatdreamscost():
    return import_module(".integrations.whatdreamscost", package=__package__)


def _scene_camera_action():
    return import_module(".integrations.scene_camera_action", package=__package__)


def _minimax_h3_turbo():
    return import_module(".integrations.minimax_h3_turbo", package=__package__)


def create_minimax_h3_director_plan(*args, **kwargs):
    return _minimax_h3().create_minimax_h3_director_plan(*args, **kwargs)


def create_minimax_h3_director_workflow(*args, **kwargs):
    return finalize_workflow_result(_minimax_h3().create_minimax_h3_director_workflow(*args, **kwargs))


def find_minimax_h3_director_install(*args, **kwargs):
    return _minimax_h3().find_minimax_h3_director_install(*args, **kwargs)


def inspect_minimax_h3_director_workflow(*args, **kwargs):
    return _minimax_h3().inspect_minimax_h3_director_workflow(*args, **kwargs)


def load_minimax_h3_director_profile(*args, **kwargs):
    return _minimax_h3().load_minimax_h3_director_profile(*args, **kwargs)

CATEGORY = "Pi Agent"


def _string_input(default: str = "", multiline: bool = True) -> tuple:
    options: dict[str, Any] = {"default": default}
    if multiline:
        options["multiline"] = True
    return ("STRING", options)


class PiAgentStatus:
    CATEGORY = f"{CATEGORY}/Runtime"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status_json", "message")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"pi_executable": _string_input("", False)}}

    def run(self, pi_executable: str):
        status = discover_pi(pi_executable).to_dict()
        status["plugin_version"] = __version__
        return (json_text(status), status["message"])


class PiAgentPrompt:
    CATEGORY = f"{CATEGORY}/Runtime"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("response", "result_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Explain what this ComfyUI project needs."),
            "provider": _string_input("", False),
            "model": _string_input("", False),
            "project_directory": _string_input("", False),
            "pi_executable": _string_input("", False),
            "timeout_seconds": ("INT", {"default": 180, "min": 10, "max": 3600})
        }, "optional": {
            "workflow_json_or_path": _string_input("{}"),
        }}

    def run(self, request, provider, model, project_directory, pi_executable, timeout_seconds, workflow_json_or_path="{}"):
        workflow = load_json(workflow_json_or_path, default={})
        result = run_pi_prompt(
            request, provider, model, project_directory, pi_executable, timeout_seconds,
            workflow=workflow,
        )
        text = result.get("text") or result.get("error") or ""
        return (text, json_text(result))


class PiIntegrationContextRouter:
    CATEGORY = f"{CATEGORY}/Runtime"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("routing_json", "context_preview")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "message": _string_input("Describe the node pack or workflow task."),
            "workflow_json_or_path": _string_input("{}"),
            "include_context_preview": ("BOOLEAN", {"default": False}),
        }}

    def run(self, message, workflow_json_or_path, include_context_preview):
        workflow = load_json(workflow_json_or_path, default={})
        if include_context_preview:
            integrations = build_dynamic_integration_context(workflow=workflow, message=message)
        else:
            integrations = integration_status(workflow=workflow, message=message)
        guidance = build_request_guidance(message, workflow=workflow)
        routed = {
            "integrations": integrations,
            "loaded_skills": guidance.get("loaded_skills", []),
            "task_envelope": guidance.get("task_envelope", ""),
        }
        preview_parts = []
        if include_context_preview:
            if guidance.get("skill_context"):
                preview_parts.append(str(guidance["skill_context"]))
            if isinstance(integrations, dict) and integrations.get("context"):
                preview_parts.append(str(integrations["context"]))
        return (json_text(routed), "\n\n---\n\n".join(preview_parts))


class PiWorkflowAnalyze:
    CATEGORY = f"{CATEGORY}/Workflow Intelligence"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("report_json", "summary")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}")}}

    def run(self, workflow_json_or_path):
        report = analyze_workflow(workflow_json_or_path).to_dict()
        summary = f"Format: {report['format']}; nodes: {report['node_count']}; links: {report['link_count']}; issues: {len(report['issues'])}."
        return (json_text(report), summary)


class PiWorkflowValidate:
    CATEGORY = f"{CATEGORY}/Workflow Intelligence"
    RETURN_TYPES = ("BOOLEAN", "STRING")
    RETURN_NAMES = ("valid", "report_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}"), "strict": ("BOOLEAN", {"default": False})}}

    def run(self, workflow_json_or_path, strict):
        result = validate_workflow(workflow_json_or_path, strict)
        return (result["valid"], json_text(result))


class PiWorkflowRepair:
    CATEGORY = f"{CATEGORY}/Workflow Intelligence"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("repaired_workflow_json", "repair_report_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}")}}

    def run(self, workflow_json_or_path):
        result = repair_workflow(workflow_json_or_path)
        return (json_text(result["repaired"]), json_text({k: v for k, v in result.items() if k not in {"original", "repaired"}}))


class PiWorkflowFinalize:
    CATEGORY = f"{CATEGORY}/Workflow Intelligence"
    RETURN_TYPES = ("BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("valid", "finalized_workflow_json", "gate_report_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "workflow_json_or_path": _string_input("{}"),
            "organize_nodes": ("BOOLEAN", {"default": True}),
            "minimum_node_gap_px": ("INT", {"default": 6, "min": 6, "max": 1000}),
        }}

    def run(self, workflow_json_or_path, organize_nodes, minimum_node_gap_px):
        result = finalize_generated_workflow(
            workflow_json_or_path,
            minimum_gap=max(6, int(minimum_node_gap_px)),
            organize=bool(organize_nodes),
        )
        return (
            result["valid"],
            json_text(result["workflow"]),
            json_text({key: value for key, value in result.items() if key != "workflow"}),
        )


class PiModelInventory:
    CATEGORY = f"{CATEGORY}/Models"
    RETURN_TYPES = ("MODEL_INVENTORY", "STRING")
    RETURN_NAMES = ("inventory", "inventory_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"limit_per_category": ("INT", {"default": 500, "min": 1, "max": 10000})}}

    def run(self, limit_per_category):
        result = inventory_models(limit_per_category)
        return (result, json_text(result))


class PiModelResolver:
    CATEGORY = f"{CATEGORY}/Models"
    RETURN_TYPES = ("MODEL_PROFILE", "STRING")
    RETURN_NAMES = ("model_profile", "profile_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model_family": _string_input("qwen-image-edit", False),
            "preferred_format": (["auto", "safetensors", "gguf", "ckpt", "pt"],),
            "inventory_json": _string_input("")
        }}

    def run(self, model_family, preferred_format, inventory_json):
        result = resolve_model(model_family, preferred_format, inventory_json or None)
        return (result, json_text(result))


class PiModelProfiles:
    CATEGORY = f"{CATEGORY}/Models"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("profiles_json",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"family_filter": _string_input("", False)}}

    def run(self, family_filter):
        profiles = load_profiles()
        if family_filter.strip():
            query = family_filter.lower()
            profiles = {k: v for k, v in profiles.items() if query in k.lower() or query in json.dumps(v).lower()}
        return (json_text(profiles),)


class PiPromptPackage:
    CATEGORY = f"{CATEGORY}/Prompts"
    RETURN_TYPES = ("PROMPT_PACKAGE", "STRING", "STRING")
    RETURN_NAMES = ("prompt_package", "prompt", "package_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the scene or media you want."),
            "modality": (["image", "image_edit", "video", "voice", "music", "audio", "storyboard", "reference_sheet"],),
            "model_family": _string_input("auto", False),
            "references_json": _string_input("[]"),
            "preserve": _string_input(""),
            "negative_constraints": _string_input("")
        }}

    def run(self, request, modality, model_family, references_json, preserve, negative_constraints):
        try:
            refs = load_json(references_json, default=[])
        except Exception:
            refs = []
        prompt = request.strip()
        if preserve.strip():
            prompt += f"\nPreserve: {preserve.strip()}"
        if negative_constraints.strip():
            prompt += f"\nDo not include or change: {negative_constraints.strip()}"
        package = {
            "schema_version": "1.0", "modality": modality, "model_family": model_family,
            "prompt": prompt, "references": refs, "preserve": preserve,
            "negative_constraints": negative_constraints, "status": "draft"
        }
        return (package, prompt, json_text(package))


class PiReferenceAsset:
    CATEGORY = f"{CATEGORY}/References"
    RETURN_TYPES = ("REFERENCE_ASSET", "STRING")
    RETURN_NAMES = ("reference_asset", "reference_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "reference_type": (["character_sheet", "voice_reference", "music_reference", "audio_reference", "moodboard", "storyboard", "environment_sheet", "prop_sheet", "visual_bible"],),
            "title": _string_input("Reference", False),
            "description": _string_input(""),
            "roles": _string_input("identity, style", False),
            "source_files": _string_input("")
        }}

    def run(self, reference_type, title, description, roles, source_files):
        result = create_reference_asset(reference_type, title, description, roles, source_files)
        return (result, json_text(result))



class PiImageWorkflowPlan:
    CATEGORY = f"{CATEGORY}/Image"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the image or edit."),
            "model_family": (["qwen-image", "qwen-image-edit", "krea-2", "krea-2-edit", "flux-2-klein", "z-image"],),
            "mode": (["text_to_image", "image_edit", "multi_reference", "inpaint", "outpaint", "style_reference", "character_reference"],),
            "references_json": _string_input("[]"),
            "preferred_format": (["auto", "safetensors", "gguf"],),
            "speed_preference": (["quality", "balanced", "fast"],),
            "quality_preference": (["maximum", "balanced", "draft"],)
        }}

    def run(self, request, model_family, mode, references_json, preferred_format, speed_preference, quality_preference):
        result = create_image_workflow_plan(request, model_family, mode, references_json, preferred_format, speed_preference, quality_preference)
        return (result, json_text(result))


class PiQwenImageEditPlan:
    CATEGORY = f"{CATEGORY}/Image"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe exactly what should change and what must stay the same."),
            "references_json": _string_input("[]"),
            "mode": (["image_edit", "multi_reference", "text_edit", "inpaint", "outpaint"],),
            "preferred_format": (["auto", "safetensors", "gguf"],)
        }}

    def run(self, request, references_json, mode, preferred_format):
        result = create_image_workflow_plan(request, "qwen-image-edit", mode, references_json, preferred_format)
        return (result, json_text(result))


class PiKrea2EditPlan:
    CATEGORY = f"{CATEGORY}/Image"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the edit and preservation requirements."),
            "references_json": _string_input("[]"),
            "variant": (["turbo", "raw", "identity_edit"],),
            "preferred_format": (["auto", "safetensors", "gguf"],)
        }}

    def run(self, request, references_json, variant, preferred_format):
        result = create_image_workflow_plan(request, "krea-2-edit", variant, references_json, preferred_format)
        return (result, json_text(result))


class PiMiniMaxH3DirectorStatus:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Director"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status_json", "summary")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"include_profile": ("BOOLEAN", {"default": True})}}

    def run(self, include_profile):
        status = find_minimax_h3_director_install()
        if include_profile:
            status["profile"] = load_minimax_h3_director_profile()
        summary = (
            "MiniMax H3 Director detected." if status.get("installed")
            else "MiniMax H3 Director is not detected. ComfyUI-Pi still knows the integration, but will not claim Director workflows are runnable until the pack is installed."
        )
        return (json_text(status), summary)


class PiMiniMaxH3DirectorPlan:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Director"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the MiniMax H3 shot or sequence."),
            "mode": (["auto", "fl2va", "ref2va"],),
            "duration_seconds": ("FLOAT", {"default": 5.0, "min": 0.1, "max": 60.0, "step": 0.1}),
            "prompt_format": (["minimax", "comfyui"],),
            "reference_images": ("INT", {"default": 0, "min": 0, "max": 99}),
            "reference_videos": ("INT", {"default": 0, "min": 0, "max": 99}),
            "reference_audios": ("INT", {"default": 0, "min": 0, "max": 99}),
            "use_preview_override": ("BOOLEAN", {"default": True}),
            "use_enhance_prompt": ("BOOLEAN", {"default": False}),
            "retake": ("BOOLEAN", {"default": False}),
        }}

    def run(self, request, mode, duration_seconds, prompt_format, reference_images, reference_videos, reference_audios, use_preview_override, use_enhance_prompt, retake):
        result = create_minimax_h3_director_plan(
            request=request, mode=mode, duration_seconds=duration_seconds,
            prompt_format=prompt_format, reference_images=reference_images,
            reference_videos=reference_videos, reference_audios=reference_audios,
            use_preview_override=use_preview_override, use_enhance_prompt=use_enhance_prompt,
            retake=retake,
        )
        return (result, json_text(result))


class PiMiniMaxH3DirectorWorkflow:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Director"
    RETURN_TYPES = ("COMFY_WORKFLOW", "STRING", "STRING")
    RETURN_NAMES = ("workflow", "workflow_json", "result_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Create a MiniMax H3 Director workflow for this shot."),
            "mode": (["auto", "fl2va", "ref2va"],),
            "duration_seconds": ("FLOAT", {"default": 5.0, "min": 0.1, "max": 60.0, "step": 0.1}),
            "prompt_format": (["minimax", "comfyui"],),
            "reference_images": ("INT", {"default": 0, "min": 0, "max": 99}),
            "reference_videos": ("INT", {"default": 0, "min": 0, "max": 99}),
            "reference_audios": ("INT", {"default": 0, "min": 0, "max": 99}),
            "use_preview_override": ("BOOLEAN", {"default": True}),
            "use_enhance_prompt": ("BOOLEAN", {"default": False}),
            "retake": ("BOOLEAN", {"default": False}),
        }}

    def run(self, request, mode, duration_seconds, prompt_format, reference_images, reference_videos, reference_audios, use_preview_override, use_enhance_prompt, retake):
        result = create_minimax_h3_director_workflow(
            request=request, mode=mode, duration_seconds=duration_seconds,
            prompt_format=prompt_format, reference_images=reference_images,
            reference_videos=reference_videos, reference_audios=reference_audios,
            use_preview_override=use_preview_override, use_enhance_prompt=use_enhance_prompt,
            retake=retake,
        )
        workflow = result.get("workflow") or {}
        return (workflow, json_text(workflow), json_text({k: v for k, v in result.items() if k != "workflow"}))


class PiMiniMaxH3DirectorInspect:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Director"
    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("inspection_json", "detected")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}")}}

    def run(self, workflow_json_or_path):
        result = inspect_minimax_h3_director_workflow(workflow_json_or_path)
        return (json_text(result), bool(result.get("detected")))


class PiWhatDreamsCostStatus:
    CATEGORY = f"{CATEGORY}/Video/WhatDreamsCost"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status_json", "summary")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"include_profile": ("BOOLEAN", {"default": True})}}

    def run(self, include_profile):
        module = _whatdreamscost()
        status = module.find_whatdreamscost_install()
        if include_profile:
            status["profile"] = module.load_whatdreamscost_profile()
        summary = (
            "WhatDreamsCost-ComfyUI detected." if status.get("installed")
            else "WhatDreamsCost-ComfyUI is not detected. ComfyUI-Pi knows how to work with it but will not claim its workflows are runnable until the pack is installed."
        )
        return (json_text(status), summary)


class PiWhatDreamsCostPlan:
    CATEGORY = f"{CATEGORY}/Video/WhatDreamsCost"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the LTX Director or WhatDreamsCost workflow."),
            "workflow_mode": (["director", "custom_audio", "fflf_2_stage", "fflf_3_stage"],),
            "preferred_format": (["auto", "safetensors", "gguf"],),
            "use_prompt_relay": ("BOOLEAN", {"default": True}),
            "use_custom_audio": ("BOOLEAN", {"default": False}),
            "use_ic_lora": ("BOOLEAN", {"default": False}),
            "retake": ("BOOLEAN", {"default": False}),
        }}

    def run(self, request, workflow_mode, preferred_format, use_prompt_relay, use_custom_audio, use_ic_lora, retake):
        result = _whatdreamscost().create_whatdreamscost_plan(
            request=request, workflow_mode=workflow_mode, preferred_format=preferred_format,
            use_prompt_relay=use_prompt_relay, use_custom_audio=use_custom_audio,
            use_ic_lora=use_ic_lora, retake=retake,
        )
        return (result, json_text(result))


class PiWhatDreamsCostWorkflow:
    CATEGORY = f"{CATEGORY}/Video/WhatDreamsCost"
    RETURN_TYPES = ("COMFY_WORKFLOW", "STRING", "STRING")
    RETURN_NAMES = ("workflow", "workflow_json", "result_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Create a WhatDreamsCost/LTX workflow for this task."),
            "workflow_mode": (["director", "custom_audio", "fflf_2_stage", "fflf_3_stage"],),
            "preferred_format": (["auto", "safetensors", "gguf"],),
            "use_prompt_relay": ("BOOLEAN", {"default": True}),
            "use_custom_audio": ("BOOLEAN", {"default": False}),
            "use_ic_lora": ("BOOLEAN", {"default": False}),
            "retake": ("BOOLEAN", {"default": False}),
        }}

    def run(self, request, workflow_mode, preferred_format, use_prompt_relay, use_custom_audio, use_ic_lora, retake):
        result = finalize_workflow_result(_whatdreamscost().create_whatdreamscost_workflow(
            request=request, workflow_mode=workflow_mode, preferred_format=preferred_format,
            use_prompt_relay=use_prompt_relay, use_custom_audio=use_custom_audio,
            use_ic_lora=use_ic_lora, retake=retake,
        ))
        workflow = result.get("workflow") or {}
        return (workflow, json_text(workflow), json_text({k: v for k, v in result.items() if k != "workflow"}))


class PiWhatDreamsCostInspect:
    CATEGORY = f"{CATEGORY}/Video/WhatDreamsCost"
    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("inspection_json", "detected")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}")}}

    def run(self, workflow_json_or_path):
        result = _whatdreamscost().inspect_whatdreamscost_workflow(workflow_json_or_path)
        return (json_text(result), bool(result.get("detected")))


class PiSceneCameraActionStatus:
    CATEGORY = f"{CATEGORY}/Video/Scene Camera Action"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status_json", "summary")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"include_profile": ("BOOLEAN", {"default": True})}}

    def run(self, include_profile):
        module = _scene_camera_action()
        status = module.find_scene_camera_action_install()
        if include_profile:
            status["profile"] = module.load_scene_camera_action_profile()
        summary = (
            "ComfyUI Scene Camera Action detected." if status.get("installed")
            else "ComfyUI Scene Camera Action is not detected. ComfyUI-Pi can still plan and author SceneState guidance, but will not claim the interactive nodes are runnable until the pack is installed."
        )
        return (json_text(status), summary)


class PiSceneCameraActionPlan:
    CATEGORY = f"{CATEGORY}/Video/Scene Camera Action"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the 3D staging, actor movement, and camera previz task."),
            "actor_type": (["human", "car"],),
            "duration_seconds": ("FLOAT", {"default": 7.0, "min": 4.0, "max": 15.0, "step": 0.5}),
            "include_directing": ("BOOLEAN", {"default": True}),
            "scene_source": (["generated", "preset", "existing"],),
        }}

    def run(self, request, actor_type, duration_seconds, include_directing, scene_source):
        result = _scene_camera_action().create_scene_camera_action_plan(
            request=request, actor_type=actor_type, duration_seconds=duration_seconds,
            include_directing=include_directing, scene_source=scene_source,
        )
        return (result, json_text(result))


class PiSceneCameraActionWorkflow:
    CATEGORY = f"{CATEGORY}/Video/Scene Camera Action"
    RETURN_TYPES = ("COMFY_WORKFLOW", "STRING", "STRING")
    RETURN_NAMES = ("workflow", "workflow_json", "result_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Create a Scene Camera Action previz workflow for this task."),
            "actor_type": (["human", "car"],),
            "duration_seconds": ("FLOAT", {"default": 7.0, "min": 4.0, "max": 15.0, "step": 0.5}),
            "include_directing": ("BOOLEAN", {"default": True}),
            "scene_source": (["generated", "preset", "existing"],),
        }}

    def run(self, request, actor_type, duration_seconds, include_directing, scene_source):
        result = finalize_workflow_result(_scene_camera_action().create_scene_camera_action_workflow(
            request=request, actor_type=actor_type, duration_seconds=duration_seconds,
            include_directing=include_directing, scene_source=scene_source,
        ))
        workflow = result.get("workflow") or {}
        return (workflow, json_text(workflow), json_text({k: v for k, v in result.items() if k != "workflow"}))


class PiSceneCameraActionInspect:
    CATEGORY = f"{CATEGORY}/Video/Scene Camera Action"
    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("inspection_json", "detected")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}")}}

    def run(self, workflow_json_or_path):
        result = _scene_camera_action().inspect_scene_camera_action_workflow(workflow_json_or_path)
        return (json_text(result), bool(result.get("detected")))


class PiMiniMaxH3TurboStatus:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Turbo"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status_json", "summary")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"include_profile": ("BOOLEAN", {"default": True})}}

    def run(self, include_profile):
        module = _minimax_h3_turbo()
        status = module.find_minimax_h3_turbo_install()
        if include_profile:
            status["profile"] = module.load_minimax_h3_turbo_profile()
        summary = (
            "MiniMax H3 Turbo detected." if status.get("installed")
            else "MiniMax H3 Turbo is not detected. ComfyUI-Pi understands the integration but will not claim four-step Turbo workflows are runnable until the pack and LoRA are installed."
        )
        return (json_text(status), summary)


class PiMiniMaxH3TurboPlan:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Turbo"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the MiniMax H3 Turbo shot/workflow."),
            "mode": (["t2v", "i2v", "flf"],),
            "steps": ("INT", {"default": 4, "min": 4, "max": 50}),
            "lora_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "low_vram": ("BOOLEAN", {"default": False}),
        }}

    def run(self, request, mode, steps, lora_strength, low_vram):
        result = _minimax_h3_turbo().create_minimax_h3_turbo_plan(
            request=request, mode=mode, steps=steps, lora_strength=lora_strength, low_vram=low_vram,
        )
        return (result, json_text(result))


class PiMiniMaxH3TurboWorkflow:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Turbo"
    RETURN_TYPES = ("COMFY_WORKFLOW", "STRING", "STRING")
    RETURN_NAMES = ("workflow", "workflow_json", "result_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Create a MiniMax H3 Turbo workflow for this task."),
            "mode": (["t2v", "i2v", "flf"],),
            "steps": ("INT", {"default": 4, "min": 4, "max": 50}),
            "lora_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "low_vram": ("BOOLEAN", {"default": False}),
        }}

    def run(self, request, mode, steps, lora_strength, low_vram):
        result = finalize_workflow_result(_minimax_h3_turbo().create_minimax_h3_turbo_workflow(
            request=request, mode=mode, steps=steps, lora_strength=lora_strength, low_vram=low_vram,
        ))
        workflow = result.get("workflow") or {}
        return (workflow, json_text(workflow), json_text({k: v for k, v in result.items() if k != "workflow"}))


class PiMiniMaxH3TurboInspect:
    CATEGORY = f"{CATEGORY}/Video/MiniMax H3 Turbo"
    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("inspection_json", "detected")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workflow_json_or_path": _string_input("{}")}}

    def run(self, workflow_json_or_path):
        result = _minimax_h3_turbo().inspect_minimax_h3_turbo_workflow(workflow_json_or_path)
        return (json_text(result), bool(result.get("detected")))


class PiAudioWorkflowPlan:
    CATEGORY = f"{CATEGORY}/Audio"
    RETURN_TYPES = ("WORKFLOW_PLAN", "STRING")
    RETURN_NAMES = ("workflow_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Describe the speech, music, ambience, or sound."),
            "model_family": (["ace-step-1.5", "qwen3-tts", "stable-audio-3"],),
            "mode": _string_input("auto", False),
            "reference_audio": _string_input("", False),
            "duration_seconds": ("FLOAT", {"default": 30.0, "min": 0.1, "max": 3600.0, "step": 0.1}),
            "language": _string_input("en", False),
            "preferred_format": (["auto", "safetensors", "gguf", "sidecar", "api"],)
        }}

    def run(self, request, model_family, mode, reference_audio, duration_seconds, language, preferred_format):
        result = create_audio_workflow_plan(request, model_family, mode, reference_audio, duration_seconds, language, preferred_format)
        return (result, json_text(result))


class PiCharacterSheetPlan:
    CATEGORY = f"{CATEGORY}/References"
    RETURN_TYPES = ("REFERENCE_PLAN", "STRING")
    RETURN_NAMES = ("reference_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "description": _string_input("Describe the canonical character."),
            "views": _string_input("front, three-quarter front, profile, rear", False),
            "expressions": _string_input("neutral, happy, sad, angry", False),
            "wardrobe_variants": _string_input("canonical", False),
            "model_family": (["qwen-image-edit", "krea-2-edit", "flux-2-klein", "z-image"],)
        }}

    def run(self, description, views, expressions, wardrobe_variants, model_family):
        result = create_character_sheet_plan(description, views, expressions, wardrobe_variants, model_family)
        return (result, json_text(result))


class PiMoodBoardPlan:
    CATEGORY = f"{CATEGORY}/References"
    RETURN_TYPES = ("REFERENCE_ASSET", "STRING")
    RETURN_NAMES = ("moodboard", "moodboard_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "title": _string_input("Visual Direction", False),
            "direction": _string_input("Describe the visual mood, style, and production intent."),
            "categories": _string_input("color, lighting, composition, materials, atmosphere", False),
            "source_references_json": _string_input("[]")
        }}

    def run(self, title, direction, categories, source_references_json):
        result = create_moodboard_plan(title, direction, categories, source_references_json)
        return (result, json_text(result))


class PiStoryboardPlan:
    CATEGORY = f"{CATEGORY}/References"
    RETURN_TYPES = ("STORYBOARD", "STRING")
    RETURN_NAMES = ("storyboard", "storyboard_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "shot_list_json": _string_input("{\"shots\": []}"),
            "style_reference": _string_input("", False),
            "detail_level": (["thumbnail", "detailed", "technical"],)
        }}

    def run(self, shot_list_json, style_reference, detail_level):
        result = create_storyboard_plan(shot_list_json, style_reference, detail_level)
        return (result, json_text(result))


class PiProductionBible:
    CATEGORY = f"{CATEGORY}/References"
    RETURN_TYPES = ("PRODUCTION_BIBLE", "STRING")
    RETURN_NAMES = ("bible", "bible_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "bible_type": (["story", "series", "character", "world", "location", "continuity", "visual", "cinematography", "voice", "music", "sound", "workflow", "production"],),
            "title": _string_input("Project Bible", False),
            "source_text": _string_input(""),
            "entries_json": _string_input("[]")
        }}

    def run(self, bible_type, title, source_text, entries_json):
        result = create_bible(bible_type, title, source_text, entries_json)
        return (result, json_text(result))


class PiProductionBuildPlan:
    CATEGORY = f"{CATEGORY}/Production"
    RETURN_TYPES = ("PRODUCTION_BUILD_PLAN", "STRING")
    RETURN_NAMES = ("build_plan", "build_plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "project_json": _string_input("{}"),
            "compile_mode": (["fresh", "resume", "incremental", "repair", "rebuild", "validate_only", "dry_run"],),
            "compile_target": (["plan", "writing", "screenplay", "preproduction", "references", "storyboards", "prompts", "workflows", "media", "editorial", "nle", "documentation", "complete"],),
            "scope_type": (["project", "sequence", "scene", "shot", "character", "location", "reference", "workflow", "asset", "document"],),
            "scope_ids": _string_input("", False)
        }}

    def run(self, project_json, compile_mode, compile_target, scope_type, scope_ids):
        result = create_build_plan(project_json, compile_mode, compile_target, scope_type, scope_ids)
        return (result, json_text(result))


class PiFountainScreenplay:
    CATEGORY = f"{CATEGORY}/Writing"
    RETURN_TYPES = ("FOUNTAIN_SCRIPT", "STRING")
    RETURN_NAMES = ("fountain_script", "fountain_text")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "title": _string_input("Untitled", False),
            "author": _string_input("", False),
            "story_or_scene_text": _string_input("Describe the action."),
            "default_location": _string_input("UNSPECIFIED LOCATION", False)
        }}

    def run(self, title, author, story_or_scene_text, default_location):
        text = build_fountain(title, author, story_or_scene_text, default_location)
        script = {"title": title, "author": author, "text": text, "parsed": parse_fountain(text)}
        return (script, text)


class PiFountainParse:
    CATEGORY = f"{CATEGORY}/Writing"
    RETURN_TYPES = ("FOUNTAIN_SCRIPT", "STRING", "BOOLEAN")
    RETURN_NAMES = ("fountain_script", "parsed_json", "valid")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"fountain_text": _string_input("")}}

    def run(self, fountain_text):
        result = validate_fountain(fountain_text)
        script = {"text": fountain_text, "parsed": result["parsed"], "validation": {"valid": result["valid"], "issues": result["issues"]}}
        return (script, json_text(result["parsed"]), result["valid"])


class PiScreenplayBreakdown:
    CATEGORY = f"{CATEGORY}/Writing"
    RETURN_TYPES = ("SCREENPLAY_BREAKDOWN", "STRING")
    RETURN_NAMES = ("breakdown", "breakdown_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"fountain_script_or_text": ("FOUNTAIN_SCRIPT",)}}

    def run(self, fountain_script_or_text):
        text = fountain_script_or_text.get("text", "") if isinstance(fountain_script_or_text, dict) else str(fountain_script_or_text)
        result = screenplay_breakdown(text)
        return (result, json_text(result))


class PiShotList:
    CATEGORY = f"{CATEGORY}/Writing"
    RETURN_TYPES = ("SHOT_LIST", "STRING")
    RETURN_NAMES = ("shot_list", "shot_list_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"screenplay_breakdown": ("SCREENPLAY_BREAKDOWN",), "coverage": (["minimal", "standard", "detailed"],)}}

    def run(self, screenplay_breakdown, coverage):
        result = create_shot_list(screenplay_breakdown, coverage)
        return (result, json_text(result))


class PiProjectPlan:
    CATEGORY = f"{CATEGORY}/Production"
    RETURN_TYPES = ("PRODUCTION_PLAN", "STRING")
    RETURN_NAMES = ("production_plan", "plan_json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Create a complete production project."),
            "project_name": _string_input("", False),
            "production_type": (["auto", "short_video", "short_film", "feature_film", "episode", "music_video", "animation", "game_cinematic"],),
            "target_nle": (["kdenlive", "generic_otio"],)
        }}

    def run(self, request, project_name, production_type, target_nle):
        result = create_project_plan(request, project_name, production_type, target_nle)
        return (result, json_text(result))


class PiProjectCompile:
    CATEGORY = f"{CATEGORY}/Production"
    RETURN_TYPES = ("PRODUCTION_PROJECT", "STRING", "STRING")
    RETURN_NAMES = ("production_project", "project_root", "result_json")
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "request": _string_input("Create a complete production project."),
            "project_name": _string_input("", False),
            "output_directory": _string_input("", False),
            "production_type": (["auto", "short_video", "short_film", "feature_film", "episode", "music_video", "animation", "game_cinematic"],),
            "target_nle": (["kdenlive", "generic_otio"],)
        }}

    def run(self, request, project_name, output_directory, production_type, target_nle):
        result = compile_project(request, project_name, output_directory, production_type, target_nle)
        project = {"root": result["project_root"], "plan": result["plan"], "manifest": result["manifest"], "asset_catalog": result.get("asset_catalog", {}), "directory_layout": result.get("directory_layout", [])}
        return (project, result["project_root"], json_text(result))


class PiCompleteProduction(PiProjectCompile):
    CATEGORY = f"{CATEGORY}/Production"


class PiSkillCreate:
    CATEGORY = f"{CATEGORY}/Skills"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("skill_directory", "manifest_json")
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "project_directory": _string_input("", False),
            "name": _string_input("my-comfyui-skill", False),
            "description": _string_input("Explain what the skill does."),
            "instructions": _string_input("Describe the steps the agent must follow.")
        }}

    def run(self, project_directory, name, description, instructions):
        result = create_skill(project_directory, name, description, instructions)
        return (result["skill_directory"], json_text(result["manifest"]))


class PiTutorialCompile:
    CATEGORY = f"{CATEGORY}/Tutorials"
    RETURN_TYPES = ("TUTORIAL_PROJECT", "STRING", "STRING")
    RETURN_NAMES = ("tutorial_project", "tutorial_directory", "result_json")
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "workflows_json_or_paths": _string_input("[]"),
            "title": _string_input("ComfyUI Project Tutorial", False),
            "output_directory": _string_input("", False),
            "detail_level": (["quick_start", "standard", "complete", "instructor", "developer"],)
        }}

    def run(self, workflows_json_or_paths, title, output_directory, detail_level):
        result = compile_tutorial(workflows_json_or_paths, title, output_directory, detail_level)
        return (result["tutorial"], result["tutorial_directory"], json_text({k: v for k, v in result.items() if k != "tutorial"}))


class PiTutorialLoad:
    CATEGORY = f"{CATEGORY}/Tutorials"
    RETURN_TYPES = ("TUTORIAL_PROJECT", "STRING")
    RETURN_NAMES = ("tutorial", "json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tutorial_directory": _string_input("", False)}}

    def run(self, tutorial_directory):
        tutorial = load_tutorial(tutorial_directory)
        tutorial["tutorial_directory"] = str(Path(tutorial_directory).expanduser().resolve())
        return (tutorial, json_text(tutorial))


class PiTutorialPreflight:
    CATEGORY = f"{CATEGORY}/Tutorials"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tutorial": ("TUTORIAL_PROJECT",), "mode": (["standard", "strict"],)}}

    def run(self, tutorial, mode):
        return (json_text(tutorial_preflight(tutorial, mode)),)


class PiTutorialStageSelect:
    CATEGORY = f"{CATEGORY}/Tutorials"
    RETURN_TYPES = ("TUTORIAL_STAGE", "STRING")
    RETURN_NAMES = ("stage", "json")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tutorial": ("TUTORIAL_PROJECT",), "stage_number": ("INT", {"default": 1, "min": 1, "max": 999})}}

    def run(self, tutorial, stage_number):
        stage = select_stage(tutorial, stage_number)
        return (stage, json_text(stage))


class PiTutorialStageValidate:
    CATEGORY = f"{CATEGORY}/Tutorials"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"stage": ("TUTORIAL_STAGE",), "mode": (["check_files", "structural"],)}}

    def run(self, stage, mode):
        return (json_text(validate_stage(stage, mode)),)


class PiTutorialNote:
    CATEGORY = f"{CATEGORY}/Tutorials"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"heading": _string_input("Tutorial Note", False), "text": _string_input("")}}

    def run(self, heading, text):
        return (f"{heading}\n\n{text}",)


class PiMarkdownSave:
    CATEGORY = f"{CATEGORY}/Documents"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"markdown": _string_input("# Document"), "output_directory": _string_input("", False), "filename": _string_input("document.md", False)}}

    def run(self, markdown, output_directory, filename):
        root = resolve_output_root(output_directory, "documents")
        name = filename if filename.lower().endswith(".md") else filename + ".md"
        path = safe_join(root, slugify(Path(name).stem) + ".md")
        atomic_write_text(path, markdown)
        return (str(path),)


class PiDocxExport:
    CATEGORY = f"{CATEGORY}/Documents"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"markdown": _string_input("# Document"), "output_directory": _string_input("", False), "filename": _string_input("document.docx", False), "title": _string_input("Document", False)}}

    def run(self, markdown, output_directory, filename, title):
        root = resolve_output_root(output_directory, "documents")
        name = filename if filename.lower().endswith(".docx") else filename + ".docx"
        path = safe_join(root, slugify(Path(name).stem) + ".docx")
        write_docx(path, markdown, title)
        return (str(path),)


class PiJsonSave:
    CATEGORY = f"{CATEGORY}/Documents"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"json_text": _string_input("{}"), "output_directory": _string_input("", False), "filename": _string_input("data.json", False)}}

    def run(self, json_text, output_directory, filename):
        payload = load_json(json_text, default={})
        root = resolve_output_root(output_directory, "documents")
        name = filename if filename.lower().endswith(".json") else filename + ".json"
        path = safe_join(root, slugify(Path(name).stem) + ".json")
        atomic_write_json(path, payload)
        return (str(path),)


class PiKdenlivePackage:
    CATEGORY = f"{CATEGORY}/NLE"
    RETURN_TYPES = ("NLE_PROJECT", "STRING", "STRING")
    RETURN_NAMES = ("nle_project", "project_path", "result_json")
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"production_manifest_json": _string_input("{}"), "output_directory": _string_input("", False), "project_name": _string_input("", False)}}

    def run(self, production_manifest_json, output_directory, project_name):
        result = create_kdenlive_package(production_manifest_json, output_directory, project_name)
        nle = {"type": "kdenlive", **result}
        return (nle, result["kdenlive_project"], json_text(result))


class PiShowText:
    CATEGORY = f"{CATEGORY}/Utility"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": _string_input("")}}

    def run(self, text):
        return (text,)


NODE_CLASS_MAPPINGS = {
    "PiAgentStatus": PiAgentStatus,
    "PiAgentPrompt": PiAgentPrompt,
    "PiIntegrationContextRouter": PiIntegrationContextRouter,
    "PiWorkflowAnalyze": PiWorkflowAnalyze,
    "PiWorkflowValidate": PiWorkflowValidate,
    "PiWorkflowRepair": PiWorkflowRepair,
    "PiWorkflowFinalize": PiWorkflowFinalize,
    "PiModelInventory": PiModelInventory,
    "PiModelResolver": PiModelResolver,
    "PiModelProfiles": PiModelProfiles,
    "PiPromptPackage": PiPromptPackage,
    "PiReferenceAsset": PiReferenceAsset,
    "PiImageWorkflowPlan": PiImageWorkflowPlan,
    "PiQwenImageEditPlan": PiQwenImageEditPlan,
    "PiKrea2EditPlan": PiKrea2EditPlan,
    "PiMiniMaxH3DirectorStatus": PiMiniMaxH3DirectorStatus,
    "PiMiniMaxH3DirectorPlan": PiMiniMaxH3DirectorPlan,
    "PiMiniMaxH3DirectorWorkflow": PiMiniMaxH3DirectorWorkflow,
    "PiMiniMaxH3DirectorInspect": PiMiniMaxH3DirectorInspect,
    "PiWhatDreamsCostStatus": PiWhatDreamsCostStatus,
    "PiWhatDreamsCostPlan": PiWhatDreamsCostPlan,
    "PiWhatDreamsCostWorkflow": PiWhatDreamsCostWorkflow,
    "PiWhatDreamsCostInspect": PiWhatDreamsCostInspect,
    "PiSceneCameraActionStatus": PiSceneCameraActionStatus,
    "PiSceneCameraActionPlan": PiSceneCameraActionPlan,
    "PiSceneCameraActionWorkflow": PiSceneCameraActionWorkflow,
    "PiSceneCameraActionInspect": PiSceneCameraActionInspect,
    "PiMiniMaxH3TurboStatus": PiMiniMaxH3TurboStatus,
    "PiMiniMaxH3TurboPlan": PiMiniMaxH3TurboPlan,
    "PiMiniMaxH3TurboWorkflow": PiMiniMaxH3TurboWorkflow,
    "PiMiniMaxH3TurboInspect": PiMiniMaxH3TurboInspect,
    "PiAudioWorkflowPlan": PiAudioWorkflowPlan,
    "PiCharacterSheetPlan": PiCharacterSheetPlan,
    "PiMoodBoardPlan": PiMoodBoardPlan,
    "PiStoryboardPlan": PiStoryboardPlan,
    "PiProductionBible": PiProductionBible,
    "PiProductionBuildPlan": PiProductionBuildPlan,
    "PiFountainScreenplay": PiFountainScreenplay,
    "PiFountainParse": PiFountainParse,
    "PiScreenplayBreakdown": PiScreenplayBreakdown,
    "PiShotList": PiShotList,
    "PiProjectPlan": PiProjectPlan,
    "PiProjectCompile": PiProjectCompile,
    "PiCompleteProduction": PiCompleteProduction,
    "PiSkillCreate": PiSkillCreate,
    "PiTutorialCompile": PiTutorialCompile,
    "PiTutorialLoad": PiTutorialLoad,
    "PiTutorialPreflight": PiTutorialPreflight,
    "PiTutorialStageSelect": PiTutorialStageSelect,
    "PiTutorialStageValidate": PiTutorialStageValidate,
    "PiTutorialNote": PiTutorialNote,
    "PiMarkdownSave": PiMarkdownSave,
    "PiDocxExport": PiDocxExport,
    "PiJsonSave": PiJsonSave,
    "PiKdenlivePackage": PiKdenlivePackage,
    "PiShowText": PiShowText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PiAgentStatus": "Pi Agent Status",
    "PiAgentPrompt": "Pi Agent Prompt",
    "PiIntegrationContextRouter": "Pi Dynamic Integration Context",
    "PiWorkflowAnalyze": "Pi Analyze Workflow",
    "PiWorkflowValidate": "Pi Validate Workflow",
    "PiWorkflowRepair": "Pi Repair Workflow",
    "PiWorkflowFinalize": "Pi Finalize Generated Workflow",
    "PiModelInventory": "Pi Model Inventory",
    "PiModelResolver": "Pi Model Resolver",
    "PiModelProfiles": "Pi Model Profiles",
    "PiPromptPackage": "Pi Prompt Package",
    "PiReferenceAsset": "Pi Reference Asset",
    "PiImageWorkflowPlan": "Pi Image Workflow Plan",
    "PiQwenImageEditPlan": "Pi Qwen Image Edit Plan",
    "PiKrea2EditPlan": "Pi Krea 2 Edit Plan",
    "PiMiniMaxH3DirectorStatus": "Pi MiniMax H3 Director Status",
    "PiMiniMaxH3DirectorPlan": "Pi MiniMax H3 Director Plan",
    "PiMiniMaxH3DirectorWorkflow": "Pi MiniMax H3 Director Workflow",
    "PiMiniMaxH3DirectorInspect": "Pi Inspect MiniMax H3 Director Workflow",
    "PiWhatDreamsCostStatus": "Pi WhatDreamsCost Status",
    "PiWhatDreamsCostPlan": "Pi WhatDreamsCost Plan",
    "PiWhatDreamsCostWorkflow": "Pi WhatDreamsCost Workflow",
    "PiWhatDreamsCostInspect": "Pi Inspect WhatDreamsCost Workflow",
    "PiSceneCameraActionStatus": "Pi Scene Camera Action Status",
    "PiSceneCameraActionPlan": "Pi Scene Camera Action Plan",
    "PiSceneCameraActionWorkflow": "Pi Scene Camera Action Workflow",
    "PiSceneCameraActionInspect": "Pi Inspect Scene Camera Action Workflow",
    "PiMiniMaxH3TurboStatus": "Pi MiniMax H3 Turbo Status",
    "PiMiniMaxH3TurboPlan": "Pi MiniMax H3 Turbo Plan",
    "PiMiniMaxH3TurboWorkflow": "Pi MiniMax H3 Turbo Workflow",
    "PiMiniMaxH3TurboInspect": "Pi Inspect MiniMax H3 Turbo Workflow",
    "PiAudioWorkflowPlan": "Pi Audio Workflow Plan",
    "PiCharacterSheetPlan": "Pi Character Sheet Plan",
    "PiMoodBoardPlan": "Pi Mood Board Plan",
    "PiStoryboardPlan": "Pi Storyboard Plan",
    "PiProductionBible": "Pi Production Bible",
    "PiProductionBuildPlan": "Pi Production Build Plan",
    "PiFountainScreenplay": "Pi Fountain Screenplay",
    "PiFountainParse": "Pi Parse Fountain",
    "PiScreenplayBreakdown": "Pi Screenplay Breakdown",
    "PiShotList": "Pi Shot List",
    "PiProjectPlan": "Pi Production Plan",
    "PiProjectCompile": "Pi Compile Project",
    "PiCompleteProduction": "Pi Complete Production",
    "PiSkillCreate": "Pi Create Skill",
    "PiTutorialCompile": "Pi Compile Tutorial",
    "PiTutorialLoad": "Pi Tutorial Load",
    "PiTutorialPreflight": "Pi Tutorial Preflight",
    "PiTutorialStageSelect": "Pi Tutorial Stage Select",
    "PiTutorialStageValidate": "Pi Tutorial Stage Validate",
    "PiTutorialNote": "Pi Tutorial Note",
    "PiMarkdownSave": "Pi Save Markdown",
    "PiDocxExport": "Pi Export DOCX",
    "PiJsonSave": "Pi Save JSON",
    "PiKdenlivePackage": "Pi Kdenlive Package",
    "PiShowText": "Pi Show Text",
}
