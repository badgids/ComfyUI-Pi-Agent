from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from ..compat import get_live_node_registry
from ..io_utils import load_json

DIRECTOR_NODE_IDS = {
    "MiniMaxH3DirectorCS",
    "MiniMaxH3PreviewOverrideCS",
    "MiniMaxH3RetakeStitchCS",
    "MiniMaxH3EnhancePromptCS",
}

DIRECTOR_MAIN_NODE = "MiniMaxH3DirectorCS"
DIRECTOR_PACK_NAMES = (
    "ComfyUI-MiniMaxH3-Director",
    "comfyui-minimaxh3-director",
    "MiniMaxH3-Director",
)


def _profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "integrations" / "minimax_h3_director.json"


def load_minimax_h3_director_profile() -> dict[str, Any]:
    return json.loads(_profile_path().read_text(encoding="utf-8"))


def _candidate_custom_node_roots() -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("COMFYUI_MINIMAX_H3_DIRECTOR_PATH", "").strip()
    if explicit:
        roots.append(Path(explicit).expanduser())

    # A normal git-clone installation puts this project and the Director pack beside each
    # other under ComfyUI/custom_nodes. This is discovery, never a hardcoded machine path.
    plugin_root = Path(__file__).resolve().parents[2]
    roots.append(plugin_root.parent)

    try:
        import folder_paths  # type: ignore
        get_paths = getattr(folder_paths, "get_folder_paths", None)
        if callable(get_paths):
            for item in get_paths("custom_nodes") or []:
                roots.append(Path(item).expanduser())
    except Exception:
        pass

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def _looks_like_pack(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "minimax_director.py").is_file()
        and (path / "minimax_plan.py").is_file()
        and (path / "example_workflows").is_dir()
    )


def find_minimax_h3_director_install() -> dict[str, Any]:
    registry = get_live_node_registry()
    registered = sorted(DIRECTOR_NODE_IDS.intersection(registry.keys()))

    candidates: list[Path] = []
    explicit = os.environ.get("COMFYUI_MINIMAX_H3_DIRECTOR_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    for root in _candidate_custom_node_roots():
        if _looks_like_pack(root):
            candidates.append(root)
        if root.is_dir():
            for name in DIRECTOR_PACK_NAMES:
                candidates.append(root / name)
            try:
                for child in root.iterdir():
                    if child.is_dir() and "minimax" in child.name.lower() and "director" in child.name.lower():
                        candidates.append(child)
            except Exception:
                pass

    install: Path | None = None
    seen: set[str] = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except Exception:
            pass
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_pack(candidate):
            install = candidate
            break

    examples: list[str] = []
    if install is not None:
        example_dir = install / "example_workflows"
        try:
            examples = sorted(str(p) for p in example_dir.glob("*.json") if p.is_file())
        except Exception:
            examples = []

    return {
        "integration": "minimax-h3-director",
        "installed": bool(install or registered),
        "install_path": str(install) if install else None,
        "registered_nodes": registered,
        "all_required_nodes_registered": DIRECTOR_NODE_IDS.issubset(set(registry.keys())) if registry else False,
        "example_workflows": examples,
        "source_repository": "https://github.com/seesee75-commits/ComfyUI-MiniMaxH3-Director",
        "license": "GPL-3.0",
        "interoperability_note": "ComfyUI-Pi does not copy or bundle the Director source. It recognizes and operates an installed copy through public node IDs, live schemas, and the pack's own example workflows.",
    }


def _workflow_node_types(workflow: Any) -> list[str]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("nodes"), list):
        return [str(n.get("type")) for n in data["nodes"] if isinstance(n, dict) and n.get("type")]
    result = []
    for node in data.values():
        if isinstance(node, dict) and node.get("class_type"):
            result.append(str(node["class_type"]))
    return result


def detect_minimax_h3_director(workflow: Any = None, message: str = "") -> bool:
    if DIRECTOR_NODE_IDS.intersection(_workflow_node_types(workflow)):
        return True
    text = str(message or "").lower()
    terms = (
        "minimax h3 director", "minimaxh3director", "h3 director",
        "ref2va", "fl2va", "minimaxh3-director",
    )
    return any(term in text for term in terms)


def _director_nodes(workflow: Any) -> list[dict[str, Any]]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return []
    result: list[dict[str, Any]] = []
    if isinstance(data.get("nodes"), list):
        for node in data["nodes"]:
            if isinstance(node, dict) and str(node.get("type")) in DIRECTOR_NODE_IDS:
                result.append(node)
    else:
        for node_id, node in data.items():
            if isinstance(node, dict) and str(node.get("class_type")) in DIRECTOR_NODE_IDS:
                result.append({"id": str(node_id), **node})
    return result


def _find_ui_node(data: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [n for n in data.get("nodes", []) if isinstance(n, dict) and n.get("type") == node_type]


def _extract_director_timeline(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
    timeline = props.get("timeline_data")
    if isinstance(timeline, str):
        try:
            parsed = json.loads(timeline)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    values = node.get("widgets_values")
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and "reference_mode" in item and "segments" in item:
                try:
                    parsed = json.loads(item)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    continue
    return {}


def inspect_minimax_h3_director_workflow(workflow: Any) -> dict[str, Any]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return {"detected": False, "issues": ["Workflow is not a JSON object."], "recommendations": []}

    node_types = _workflow_node_types(data)
    detected = bool(DIRECTOR_NODE_IDS.intersection(node_types))
    issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"director_nodes": []}

    if not detected:
        return {
            "detected": False,
            "node_types": node_types,
            "issues": [],
            "warnings": [],
            "recommendations": ["No MiniMax H3 Director nodes were found."],
            "profile": load_minimax_h3_director_profile(),
        }

    main_nodes = [n for n in _director_nodes(data) if str(n.get("type") or n.get("class_type")) == DIRECTOR_MAIN_NODE]
    if not main_nodes:
        issues.append("The workflow contains Director companion nodes but no MiniMax H3 Director node.")

    # UI workflow checks are deliberately conservative: inspect known public loader values
    # without guessing widget positions inside the Director frontend state.
    if isinstance(data.get("nodes"), list):
        clip_nodes = _find_ui_node(data, "CLIPLoader")
        if clip_nodes:
            if not any(isinstance(n.get("widgets_values"), list) and "minimax" in n.get("widgets_values", []) for n in clip_nodes):
                issues.append("CLIPLoader is present but no loader is visibly configured with type 'minimax'.")
        else:
            warnings.append("No CLIPLoader was found. The Director requires a MiniMax-compatible Qwen3-VL encoder path unless the graph provides CLIP another way.")

        unets = _find_ui_node(data, "UNETLoader")
        filenames = [str(v) for n in unets for v in (n.get("widgets_values") or []) if isinstance(v, str)]
        if filenames and not any("fl2va" in v.lower() for v in filenames):
            warnings.append("No fl2va checkpoint filename was detected. Refs OFF needs minimax_h3_fl2va_* weights.")
        if filenames and not any("ref2va" in v.lower() for v in filenames):
            warnings.append("No ref2va checkpoint filename was detected. Refs ON needs minimax_h3_ref2va_* weights.")

        vaes = _find_ui_node(data, "VAELoader")
        vae_names = [str(v) for n in vaes for v in (n.get("widgets_values") or []) if isinstance(v, str)]
        if vae_names and not any("video_vae" in v.lower() for v in vae_names):
            warnings.append("No MiniMax H3 video VAE filename was detected.")
        if vae_names and not any("audio_vae" in v.lower() for v in vae_names):
            warnings.append("No MiniMax H3 audio VAE filename was detected. It is required for audio references and joint audio decode workflows.")

    for node in main_nodes:
        timeline = _extract_director_timeline(node)
        ref_mode = str(timeline.get("reference_mode", "OFF")).upper()
        segments = timeline.get("segments") if isinstance(timeline.get("segments"), list) else []
        motion = timeline.get("motionSegments") if isinstance(timeline.get("motionSegments"), list) else []
        audio = timeline.get("audioSegments") if isinstance(timeline.get("audioSegments"), list) else []
        chars = timeline.get("characters") if isinstance(timeline.get("characters"), list) else []
        character_images = sum(len(c.get("images", [])) for c in chars if isinstance(c, dict) and isinstance(c.get("images"), list))
        details["director_nodes"].append({
            "id": node.get("id"),
            "reference_mode": ref_mode,
            "prompt_format": timeline.get("prompt_format", "minimax"),
            "shot_segment_count": len(segments),
            "reference_video_count": len(motion),
            "reference_audio_count": len(audio),
            "character_reference_image_count": character_images,
            "retake_mode": bool(timeline.get("retakeMode")),
        })
        if ref_mode == "OFF" and (motion or audio or character_images):
            warnings.append("The timeline contains reference media while Refs OFF is selected. Character slots become descriptions in FL2VA; middle images/video/audio references require Refs ON/ref2VA.")
        if character_images > 9:
            issues.append("Character/reference images exceed MiniMax H3's 9-image reference limit.")
        if len(motion) > 3:
            issues.append("Reference videos exceed MiniMax H3's 3-video limit.")
        if len(audio) > 3:
            issues.append("Reference audio clips exceed MiniMax H3's 3-audio limit.")
        if character_images + len(motion) + len(audio) > 12:
            issues.append("Combined references exceed MiniMax H3's 12-file total reference limit.")

    recommendations.extend([
        "Use FL2VA/Refs OFF for text-to-video and first/last-frame anchoring.",
        "Use ref2VA/Refs ON for character slots, middle reference images, reference video, or reference audio.",
        "Keep the CLIPLoader type set to 'minimax'.",
        "Use the Director's compiled prompt preview before rendering; it is the exact prompt sent to H3.",
        "Use res_multistep with BasicGuider and approximately 20 steps as the pack's starting workflow profile; reference-heavy ref2VA may benefit from beta or normal scheduling.",
        "Decode the joint latent through the video VAE and audio VAE separately, then mux them with CreateVideo.",
        "Keep each generation within H3's trained 4-15 second range; the Director Chain node is intentionally not registered in the current pack.",
    ])

    return {
        "detected": True,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "details": details,
        "profile": load_minimax_h3_director_profile(),
        "installation": find_minimax_h3_director_install(),
    }


def create_minimax_h3_director_plan(
    request: str,
    mode: str = "auto",
    duration_seconds: float = 5.0,
    prompt_format: str = "minimax",
    reference_images: int = 0,
    reference_videos: int = 0,
    reference_audios: int = 0,
    use_preview_override: bool = True,
    use_enhance_prompt: bool = False,
    retake: bool = False,
) -> dict[str, Any]:
    profile = load_minimax_h3_director_profile()
    duration = max(0.1, float(duration_seconds))
    requested_refs = max(0, int(reference_images)) + max(0, int(reference_videos)) + max(0, int(reference_audios))
    selected_mode = mode
    if selected_mode == "auto":
        selected_mode = "ref2va" if requested_refs else "fl2va"
    if retake:
        selected_mode = "fl2va"

    warnings: list[str] = []
    if duration < 4 or duration > 15:
        warnings.append("MiniMax H3 is trained for roughly 4-15 seconds per generation. Split longer projects into shots and assemble them in the NLE.")
    if reference_images > 9:
        warnings.append("Reference image count exceeds the 9-image limit.")
    if reference_videos > 3:
        warnings.append("Reference video count exceeds the 3-video limit.")
    if reference_audios > 3:
        warnings.append("Reference audio count exceeds the 3-audio limit.")
    if requested_refs > 12:
        warnings.append("Combined references exceed the 12-file total limit.")
    if selected_mode == "fl2va" and requested_refs:
        warnings.append("FL2VA cannot use the Director's middle image/video/audio reference path. Choose ref2VA for those references.")
    if prompt_format not in {"minimax", "comfyui"}:
        warnings.append("Unknown prompt format. The Director currently documents 'minimax' and 'comfyui'.")

    return {
        "schema_version": "1.0",
        "integration": "minimax-h3-director",
        "request": request,
        "selected_conditioning_path": selected_mode,
        "checkpoint_role": "minimax_h3_ref2va_*" if selected_mode == "ref2va" else "minimax_h3_fl2va_*",
        "duration_seconds_requested": duration,
        "frame_rate": 24,
        "frame_alignment": "17k+5",
        "prompt_format": prompt_format,
        "references": {
            "images": int(reference_images),
            "videos": int(reference_videos),
            "audios": int(reference_audios),
            "total": requested_refs,
        },
        "use_preview_override": bool(use_preview_override),
        "use_enhance_prompt": bool(use_enhance_prompt),
        "retake": bool(retake),
        "sampler_profile": {
            "sampler": "res_multistep",
            "scheduler": "simple",
            "steps": 20,
            "guider": "BasicGuider",
            "cfg": "none",
            "ref2va_scheduler_note": "beta or normal can be useful for reference-heavy prompts",
        },
        "required_nodes": [DIRECTOR_MAIN_NODE] + (["MiniMaxH3PreviewOverrideCS"] if use_preview_override else []) + (["MiniMaxH3EnhancePromptCS"] if use_enhance_prompt else []) + (["MiniMaxH3RetakeStitchCS"] if retake else []),
        "required_core_roles": ["UNETLoader", "CLIPLoader(type=minimax)", "VAELoader(video)", "VAELoader(audio)", "BasicGuider", "SamplerCustomAdvanced", "VAEDecode", "VAEDecodeAudio", "CreateVideo", "SaveVideo"],
        "workflow_rules": profile["workflow_rules"],
        "warnings": warnings,
        "installation": find_minimax_h3_director_install(),
        "status": "planned",
    }


def _pick_example(install: dict[str, Any], enhance: bool) -> Path | None:
    examples = [Path(p) for p in install.get("example_workflows", [])]
    if enhance:
        matches = [p for p in examples if "enhance" in p.name.lower()]
        if matches:
            return matches[0]
    matches = [p for p in examples if "enhance" not in p.name.lower()]
    return matches[0] if matches else (examples[0] if examples else None)


def create_minimax_h3_director_workflow(
    request: str,
    mode: str = "auto",
    duration_seconds: float = 5.0,
    prompt_format: str = "minimax",
    reference_images: int = 0,
    reference_videos: int = 0,
    reference_audios: int = 0,
    use_preview_override: bool = True,
    use_enhance_prompt: bool = False,
    retake: bool = False,
) -> dict[str, Any]:
    plan = create_minimax_h3_director_plan(
        request=request,
        mode=mode,
        duration_seconds=duration_seconds,
        prompt_format=prompt_format,
        reference_images=reference_images,
        reference_videos=reference_videos,
        reference_audios=reference_audios,
        use_preview_override=use_preview_override,
        use_enhance_prompt=use_enhance_prompt,
        retake=retake,
    )
    install = plan["installation"]
    example = _pick_example(install, use_enhance_prompt)
    if example is None or not example.is_file():
        return {
            "ok": False,
            "runnable": False,
            "workflow": None,
            "source_workflow": None,
            "plan": plan,
            "error": "MiniMax H3 Director is not installed with an example workflow. ComfyUI-Pi will not fabricate a graph for an unavailable third-party node pack.",
        }

    try:
        workflow = json.loads(example.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "runnable": False,
            "workflow": None,
            "source_workflow": str(example),
            "plan": plan,
            "error": f"Could not read the Director pack's example workflow: {type(exc).__name__}: {exc}",
        }

    # Preserve the third-party example graph exactly as the creation baseline. We attach
    # requested intent as ComfyUI workflow metadata instead of guessing the timeline UI's
    # private widget serialization. The Agent can then use live schemas and the Director's
    # own frontend to make edits safely inside ComfyUI.
    workflow = copy.deepcopy(workflow)
    extra = workflow.setdefault("extra", {})
    if isinstance(extra, dict):
        extra["comfyui_pi_agent"] = {
            "integration": "minimax-h3-director",
            "request": request,
            "plan": {
                "selected_conditioning_path": plan["selected_conditioning_path"],
                "duration_seconds_requested": plan["duration_seconds_requested"],
                "prompt_format": plan["prompt_format"],
                "references": plan["references"],
                "retake": plan["retake"],
            },
            "note": "Created from the installed MiniMax H3 Director pack's own example workflow. Open it in ComfyUI and use the Director timeline editor for shot/timeline changes.",
        }

    inspection = inspect_minimax_h3_director_workflow(workflow)
    return {
        "ok": True,
        "runnable": bool(install.get("installed")),
        "workflow": workflow,
        "source_workflow": str(example),
        "plan": plan,
        "inspection": inspection,
        "editing_policy": {
            "safe": [
                "Use live ComfyUI node schemas for loader/model substitutions.",
                "Use the Director timeline frontend for timeline_data, shot segments, character slots, references, retake state, and prompt format.",
                "Preserve the original example or source workflow and return a diff for edits.",
            ],
            "avoid": [
                "Do not guess indexes in MiniMaxH3DirectorCS.widgets_values.",
                "Do not interchange fl2va and ref2va checkpoints.",
                "Do not hand-edit timeline_data unless a live-schema-aware adapter has validated the change.",
            ],
        },
    }


def build_minimax_h3_director_context(workflow: Any = None, message: str = "") -> str:
    if not detect_minimax_h3_director(workflow, message):
        return ""
    install = find_minimax_h3_director_install()
    profile = load_minimax_h3_director_profile()
    text = str(message or "").lower()
    present = set(_workflow_node_types(workflow))

    def wants(*terms: str, nodes: tuple[str, ...] = ()) -> bool:
        return any(term in text for term in terms) or bool(present.intersection(nodes))

    lines = [
        "Dynamically loaded integration knowledge: MiniMax H3 Director",
        f"Source node pack: {profile['source_repository']} (GPL-3.0).",
        "Public node IDs: " + ", ".join(profile["node_ids"]),
        "Use the installed pack's current example workflows and live /object_info schemas as runtime authority; do not guess the Director timeline's private widget serialization.",
        "FL2VA / Refs OFF uses minimax_h3_fl2va_* for text-to-video and first/last-frame anchors. ref2VA / Refs ON uses minimax_h3_ref2va_* for character slots and image/video/audio references. These checkpoints are not interchangeable.",
        "CLIPLoader type is minimax. Video and audio VAEs are separate; H3 uses a packed joint AV latent which is decoded through video and audio branches before CreateVideo muxing.",
        "H3 output is 24 fps and valid lengths align to the 17k+5 frame grid; the documented trained generation range is roughly 4-15 seconds per render.",
    ]
    if wants("ref", "reference", "character", "picture", "video reference", "audio reference", "ref2va", nodes=(DIRECTOR_MAIN_NODE,)):
        lines.append("Reference limits: <=9 images, <=3 videos (each 2-15s and <=15s total), <=3 audio clips, <=12 reference files total. Middle image/video/audio references require ref2VA; first/last keyframe anchors belong to FL2VA.")
    if wants("prompt", "storyboard", "shot", "create", "edit", "workflow", nodes=(DIRECTOR_MAIN_NODE,)):
        lines.extend([
            "MiniMax prompt format: [Shot 1] has no timestamp; later cuts use strictly increasing MM:SS.mmm timestamps. The Director compiles subject definitions, retention, detailed/storyboard description, soundscape and non-diegetic music without duplicating empty sections.",
            "Starting sampler profile in the upstream example is res_multistep, BasicGuider/no CFG, about 20 steps, usually simple scheduler; beta/normal can help reference-heavy ref2VA. Validate the installed workflow before changing it.",
            "When creating or substantially editing a workflow, begin from the installed Director pack's current example and make schema-aware changes. Do not fabricate timeline_data/widgets_values or swap FL2VA/ref2VA by filename alone.",
        ])
    if wants("preview", nodes=("MiniMaxH3PreviewOverrideCS",)):
        lines.append("MiniMaxH3PreviewOverrideCS sits between Director.model and the sampler to preview the whole shot while denoising. Its node-target preview works without VideoHelperSuite; sampler/VHS display targets need the compatible VHS installation.")
    if wants("enhance prompt", "vision model", nodes=("MiniMaxH3EnhancePromptCS",)):
        lines.append("MiniMaxH3EnhancePromptCS uses a local vision-capable endpoint to write Director-ready global or storyboard text and can pass the same images onward. In global mode it must not invent Director section labels, shot numbering, or <Picture>/<Subject> numbering that the Director owns.")
    if wants("retake", nodes=("MiniMaxH3RetakeStitchCS",)):
        lines.append("Retake Mode regenerates a marked range using surrounding base-video frames as anchors; MiniMaxH3RetakeStitchCS joins the regenerated range back to the base video/audio. Preserve retake_info and surrounding continuity.")
    if wants("long", "chain", "more than 15", "over 15"):
        lines.append("Do not plan on a shipped Director Chain node: current upstream code keeps the chain implementation unregistered. For >15s productions, split into trained-range shots/windows and assemble them editorially unless a future installed version exposes a validated chain workflow.")

    if workflow not in (None, "", {}):
        inspection = inspect_minimax_h3_director_workflow(workflow)
        lines.append("Current workflow Director inspection:\n" + json.dumps({
            "issues": inspection.get("issues", []),
            "warnings": inspection.get("warnings", []),
            "details": inspection.get("details", {}),
        }, ensure_ascii=False, indent=2))
    if install.get("installed"):
        lines.append("Installed Director status: detected. Registered nodes: " + ", ".join(install.get("registered_nodes", [])))
    else:
        lines.append("Installed Director status: not detected in this runtime. Planning/explanation can continue, but do not claim a Director workflow is executable until the pack is present.")
    return "\n".join(lines)
