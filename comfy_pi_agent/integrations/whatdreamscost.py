from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from ..compat import get_live_node_registry
from ..io_utils import load_json

WDC_NODE_IDS = {
    "LTXDirector",
    "LTXDirectorGuide",
    "LTXDirectorCropGuides",
    "LTXKeyframer",
    "MultiImageLoader",
    "LTXSequencer",
    "SpeechLengthCalculator",
    "LoadAudioUI",
    "LoadVideoUI",
}
WDC_MAIN_NODE = "LTXDirector"
WDC_PACK_NAMES = (
    "WhatDreamsCost-ComfyUI",
    "whatdreamscost-comfyui",
    "WhatDreamscost-ComfyUI",
)


def _profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "integrations" / "whatdreamscost_comfyui.json"


def load_whatdreamscost_profile() -> dict[str, Any]:
    return json.loads(_profile_path().read_text(encoding="utf-8"))


def _candidate_custom_node_roots() -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("COMFYUI_WHATDREAMSCOST_PATH", "").strip()
    if explicit:
        roots.append(Path(explicit).expanduser())

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

    result: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            root = root.resolve()
        except Exception:
            pass
        key = str(root)
        if key not in seen:
            seen.add(key)
            result.append(root)
    return result


def _looks_like_pack(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "ltx_director.py").is_file()
        and (path / "prompt_relay.py").is_file()
        and (path / "example_workflows").is_dir()
    )


def find_whatdreamscost_install() -> dict[str, Any]:
    registry = get_live_node_registry()
    registered = sorted(WDC_NODE_IDS.intersection(registry.keys()))
    candidates: list[Path] = []

    explicit = os.environ.get("COMFYUI_WHATDREAMSCOST_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    for root in _candidate_custom_node_roots():
        if _looks_like_pack(root):
            candidates.append(root)
        if root.is_dir():
            for name in WDC_PACK_NAMES:
                candidates.append(root / name)
            try:
                for child in root.iterdir():
                    low = child.name.lower()
                    if child.is_dir() and ("whatdreamscost" in low or "whatdreams" in low):
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
        try:
            examples = sorted(str(p) for p in (install / "example_workflows").glob("*.json") if p.is_file())
        except Exception:
            examples = []

    return {
        "integration": "whatdreamscost-comfyui",
        "installed": bool(install or registered),
        "install_path": str(install) if install else None,
        "registered_nodes": registered,
        "known_nodes_registered": sorted(WDC_NODE_IDS.intersection(registry.keys())) if registry else [],
        "example_workflows": examples,
        "source_repository": "https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI",
        "license": "GPL-3.0",
        "interoperability_note": (
            "ComfyUI-Pi recognizes and operates the installed node pack through public node IDs, "
            "live schemas, and the pack's own example workflows."
        ),
    }


def _workflow_node_types(workflow: Any) -> list[str]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("nodes"), list):
        return [str(n.get("type")) for n in data["nodes"] if isinstance(n, dict) and n.get("type")]
    return [
        str(node.get("class_type"))
        for node in data.values()
        if isinstance(node, dict) and node.get("class_type")
    ]


def detect_whatdreamscost(workflow: Any = None, message: str = "") -> bool:
    if WDC_NODE_IDS.intersection(_workflow_node_types(workflow)):
        return True
    text = str(message or "").lower()
    terms = (
        "whatdreamscost", "what dreams cost", "ltx director", "ltxdirector",
        "ltx sequencer", "ltx keyframer", "multi image loader",
        "speech length calculator", "load audio ui", "load video ui",
        "prompt relay", "ic-lora", "ic lora",
    )
    return any(term in text for term in terms)


def _find_ui_nodes(data: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [n for n in data.get("nodes", []) if isinstance(n, dict) and str(n.get("type")) == node_type]


def _extract_timeline(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
    for candidate in (props.get("timeline_data"),):
        if isinstance(candidate, str):
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
            except Exception:
                pass
    values = node.get("widgets_values")
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and '"segments"' in item and ('"audioSegments"' in item or '"motionSegments"' in item):
                try:
                    value = json.loads(item)
                    if isinstance(value, dict):
                        return value
                except Exception:
                    continue
    return {}


def inspect_whatdreamscost_workflow(workflow: Any) -> dict[str, Any]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return {"detected": False, "issues": ["Workflow is not a JSON object."], "warnings": [], "recommendations": []}

    node_types = _workflow_node_types(data)
    present = sorted(WDC_NODE_IDS.intersection(node_types))
    detected = bool(present)
    if not detected:
        return {
            "detected": False,
            "node_types": node_types,
            "issues": [],
            "warnings": [],
            "recommendations": ["No WhatDreamsCost nodes were found."],
            "profile": load_whatdreamscost_profile(),
        }

    issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"present_nodes": present, "directors": []}

    if isinstance(data.get("nodes"), list):
        if WDC_MAIN_NODE in present:
            clip_nodes = _find_ui_nodes(data, "CLIPLoader")
            if clip_nodes and not any(
                isinstance(n.get("widgets_values"), list) and "ltxv" in [str(v).lower() for v in n.get("widgets_values", [])]
                for n in clip_nodes
            ):
                warnings.append("No CLIPLoader visibly configured with type 'ltxv' was found. Validate the installed LTX workflow's loader type before running.")

        all_strings: list[str] = []
        for node in data.get("nodes", []):
            if not isinstance(node, dict):
                continue
            for value in node.get("widgets_values") or []:
                if isinstance(value, str):
                    all_strings.append(value)
        details["contains_gguf_model_reference"] = any(v.lower().endswith(".gguf") for v in all_strings)

        for node in _find_ui_nodes(data, WDC_MAIN_NODE):
            timeline = _extract_timeline(node)
            segments = timeline.get("segments") if isinstance(timeline.get("segments"), list) else []
            motion = timeline.get("motionSegments") if isinstance(timeline.get("motionSegments"), list) else []
            audio = timeline.get("audioSegments") if isinstance(timeline.get("audioSegments"), list) else []
            details["directors"].append({
                "id": node.get("id"),
                "segment_count": len(segments),
                "motion_segment_count": len(motion),
                "audio_segment_count": len(audio),
                "retake_mode": bool(timeline.get("retakeMode")),
                "use_custom_audio": bool(timeline.get("use_custom_audio", timeline.get("audioTrackEnabled", False))),
                "override_audio": bool(timeline.get("overrideAudio", timeline.get("override_audio", False))),
            })

            # Do not declare frontend-managed state invalid just because we cannot parse it.
            if not timeline:
                warnings.append("LTX Director was detected but its timeline state could not be safely parsed. Use the Director frontend/live schema instead of guessing widget indexes.")

    if WDC_MAIN_NODE not in present and present:
        recommendations.append("This workflow uses WhatDreamsCost utility nodes without LTX Director. Keep their live schemas and node-specific behavior separate from Director assumptions.")

    recommendations.extend([
        "Use the installed pack's own current example workflow as the preferred baseline for new LTX Director graphs.",
        "Use live ComfyUI /object_info schemas before editing node inputs, outputs, or widget values.",
        "Treat timeline_data/local_prompts/segment_lengths/guide_strength as frontend-managed state; use the timeline UI for shot/timeline edits instead of guessed widget indexes.",
        "Use Prompt Relay when multiple timed prompt segments need separate conditioning; a single prompt can take the faster non-relay path.",
        "Keep first/middle/last guide-frame intent, IC-LoRA media, custom audio, audio inpainting, and Retake Mode explicit in the production plan.",
        "When GGUF is requested, prefer the upstream LTX Director GGUF example and validate ComfyUI-GGUF plus live model/LoRA compatibility.",
    ])

    return {
        "detected": True,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "details": details,
        "profile": load_whatdreamscost_profile(),
        "installation": find_whatdreamscost_install(),
    }


def create_whatdreamscost_plan(
    request: str,
    workflow_mode: str = "director",
    preferred_format: str = "auto",
    use_prompt_relay: bool = True,
    use_custom_audio: bool = False,
    use_ic_lora: bool = False,
    retake: bool = False,
) -> dict[str, Any]:
    profile = load_whatdreamscost_profile()
    mode = str(workflow_mode or "director").lower()
    fmt = str(preferred_format or "auto").lower()
    warnings: list[str] = []
    if fmt not in {"auto", "safetensors", "gguf"}:
        warnings.append("Unknown preferred format; use auto, safetensors, or gguf.")
    if retake and mode not in {"director", "auto"}:
        warnings.append("Retake Mode is an LTX Director workflow feature; the selected non-Director mode may not support it.")
    if use_ic_lora:
        warnings.append("IC-LoRA workflows require the compatible installed LTXVideo/KJNodes components used by the current upstream workflow; validate live schemas before execution.")

    return {
        "schema_version": "1.0",
        "integration": "whatdreamscost-comfyui",
        "request": request,
        "workflow_mode": mode,
        "preferred_format": fmt,
        "features": {
            "prompt_relay": bool(use_prompt_relay),
            "custom_audio": bool(use_custom_audio),
            "ic_lora": bool(use_ic_lora),
            "retake": bool(retake),
        },
        "required_pack_nodes": [WDC_MAIN_NODE] if mode in {"director", "auto"} else [],
        "workflow_rules": profile["workflow_rules"],
        "upstream_dependencies": profile["upstream_dependencies"],
        "warnings": warnings,
        "installation": find_whatdreamscost_install(),
        "status": "planned",
    }


def _pick_example(install: dict[str, Any], mode: str, preferred_format: str) -> Path | None:
    examples = [Path(p) for p in install.get("example_workflows", [])]
    if not examples:
        return None
    mode = mode.lower()
    fmt = preferred_format.lower()

    def find_contains(*terms: str) -> Path | None:
        for path in examples:
            low = path.name.lower()
            if all(term in low for term in terms):
                return path
        return None

    if mode in {"custom_audio", "audio"}:
        found = find_contains("custom audio")
        if found:
            return found
    if mode in {"fflf_3_stage", "3_stage"}:
        found = find_contains("first last frame", "3 stage")
        if found:
            return found
    if mode in {"fflf_2_stage", "2_stage"}:
        found = find_contains("first last frame", "2 stage")
        if found:
            return found
    if fmt == "gguf":
        found = find_contains("director", "gguf")
        if found:
            return found
    found = find_contains("director", "distilled")
    if found:
        return found
    found = find_contains("director")
    return found or examples[0]


def create_whatdreamscost_workflow(
    request: str,
    workflow_mode: str = "director",
    preferred_format: str = "auto",
    use_prompt_relay: bool = True,
    use_custom_audio: bool = False,
    use_ic_lora: bool = False,
    retake: bool = False,
) -> dict[str, Any]:
    plan = create_whatdreamscost_plan(
        request=request,
        workflow_mode=workflow_mode,
        preferred_format=preferred_format,
        use_prompt_relay=use_prompt_relay,
        use_custom_audio=use_custom_audio,
        use_ic_lora=use_ic_lora,
        retake=retake,
    )
    install = plan["installation"]
    example = _pick_example(install, workflow_mode, preferred_format)
    if example is None or not example.is_file():
        return {
            "ok": False,
            "runnable": False,
            "workflow": None,
            "source_workflow": None,
            "plan": plan,
            "error": "WhatDreamsCost-ComfyUI is not installed with a usable example workflow. ComfyUI-Pi will not fabricate the pack's frontend-managed graph state.",
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
            "error": f"Could not read the installed upstream example workflow: {type(exc).__name__}: {exc}",
        }

    workflow = copy.deepcopy(workflow)
    extra = workflow.setdefault("extra", {})
    if isinstance(extra, dict):
        extra["comfyui_pi_agent"] = {
            "integration": "whatdreamscost-comfyui",
            "request": request,
            "plan": {
                "workflow_mode": plan["workflow_mode"],
                "preferred_format": plan["preferred_format"],
                "features": plan["features"],
            },
            "note": "Created from the installed WhatDreamsCost-ComfyUI pack's own current example workflow. Use the upstream timeline UI and live schemas for frontend-managed edits.",
        }
    return {
        "ok": True,
        "runnable": bool(install.get("installed")),
        "workflow": workflow,
        "source_workflow": str(example),
        "plan": plan,
        "inspection": inspect_whatdreamscost_workflow(workflow),
        "editing_policy": {
            "safe": [
                "Use live ComfyUI schemas for normal node connections and model substitutions.",
                "Use the LTX Director frontend for timeline state, shot segments, guide frames, IC-LoRA media, custom audio, and retakes.",
                "Preserve the source workflow and return a diff for edits.",
            ],
            "avoid": [
                "Do not guess LTXDirector widgets_values indexes.",
                "Do not hand-edit timeline_data unless a schema-aware adapter has validated it.",
                "Do not substitute GGUF/safetensors loaders by filename alone; rewrite the loader path and validate compatibility.",
            ],
        },
    }


def build_whatdreamscost_context(workflow: Any = None, message: str = "") -> str:
    if not detect_whatdreamscost(workflow, message):
        return ""
    profile = load_whatdreamscost_profile()
    install = find_whatdreamscost_install()
    text = str(message or "").lower()
    present = set(_workflow_node_types(workflow))

    def wants(*terms: str, nodes: tuple[str, ...] = ()) -> bool:
        return any(term in text for term in terms) or bool(present.intersection(nodes))

    lines = [
        "Dynamically loaded integration knowledge: WhatDreamsCost-ComfyUI",
        f"Source node pack: {profile['source_repository']} (GPL-3.0).",
        "Public node IDs: " + ", ".join(profile["node_ids"]),
        "Use the installed pack's live /object_info schemas and its current example workflows as runtime authority. Do not guess frontend widget indexes or stale schemas.",
    ]

    if wants("ltx director", "ltxdirector", "prompt relay", "workflow", "create", "edit", "repair", nodes=("LTXDirector",)):
        lines.extend([
            "LTX Director is a timeline editor for LTX video workflows with Prompt Relay, text/image/video guidance, first/middle/last guide frames, custom audio, audio inpainting, IC-LoRA references, Retake Mode, and timeline save/load.",
            "Frontend-managed fields include timeline_data, local_prompts, segment_lengths, and guide_strength. Use the Director frontend for timeline/shot/reference edits rather than guessing serialized widgets_values indexes.",
            "The current Director can auto-create its LTXV latent when optional_latent is absent and aligns that generated video length to LTXV's 8n+1 rule.",
            "For a single prompt segment, the current Prompt Relay path can bypass attention masking for speed; multiple timed prompt segments use Prompt Relay masking.",
            "Current upstream workflows require CLIPLoader type ltxv. Validate the installed example and live schema before changing loader settings.",
            "For new workflows, prefer the installed pack's current example: its GGUF Director example when GGUF is requested, otherwise its current distilled Director example, or the matching FFLF/custom-audio example for that task.",
        ])

    if wants("multi image loader", nodes=("MultiImageLoader",)):
        lines.append("Multi Image Loader is the pack's gallery-style image loader: it supports drag/drop, image reordering, separate or batched outputs, and combines common resize/LTX preprocessing so LTX graphs need fewer utility nodes.")
    if wants("ltx sequencer", nodes=("LTXSequencer",)):
        lines.append("LTX Sequencer is the preferred guide-frame sequencer for first/last-frame and multi-keyframe LTX shot sequences; it supports any number of middle guide frames and synchronization across Sequencer nodes.")
    if wants("ltx keyframer", nodes=("LTXKeyframer",)):
        lines.append("LTX Keyframer provides first/last/middle keyframe setup and synchronized controls; upstream documentation recommends LTX Sequencer for most current workflows when either can satisfy the task.")
    if wants("speech length calculator", nodes=("SpeechLengthCalculator",)):
        lines.append("Speech Length Calculator estimates dialogue duration in real time from quoted speech text and can feed planning for video length; treat its live schema as authority for exact outputs in the installed version.")
    if wants("load audio ui", "custom audio", "audio inpaint", nodes=("LoadAudioUI",)):
        lines.append("Load Audio UI provides ComfyUI-native audio selection/drag-drop, trimming and duration handling; current versions can scan the normal input area and the WhatDreamsCost workspace and expose filename/duration information. LTX Director can place custom audio on its timeline and optionally inpaint gaps.")
    if wants("load video ui", "crop video", "trim video", nodes=("LoadVideoUI",)):
        lines.append("Load Video UI provides drag/drop video loading, trimming, resize/crop/aspect-ratio controls, preview-oriented UI, color-conversion handling, input/workspace scanning, and filename output. Validate exact sockets live because its UI has evolved.")
    if wants("director guide", "ic-lora", "ic lora", "reference image", "reference video", nodes=("LTXDirectorGuide", "LTXDirectorCropGuides")):
        lines.append("LTX Director Guide/Crop Guides apply guide and IC-LoRA conditioning for the Director pipeline. Keep guide-frame roles, resize/crop behavior, LoRA compatibility, and the selected LTX model profile consistent; use the installed guide node schemas rather than reconstructing their internals.")
    if wants("gguf", ".gguf"):
        lines.append("For GGUF, start from the upstream LTX_Director_2_Workflow_GGUF example when installed. GGUF is a loader/subgraph choice, not a filename swap; validate ComfyUI-GGUF, model architecture, text encoder/VAE, LoRA/IC-LoRA, and live sockets.")
    if wants("retake", nodes=("LTXDirector",)) and "retake" in text:
        lines.append("Retake Mode is a Director feature for regenerating a selected range of an existing video. Preserve the surrounding/base-video continuity and use the timeline's own retake state rather than hand-authoring serialized retake fields.")

    if workflow not in (None, "", {}):
        inspection = inspect_whatdreamscost_workflow(workflow)
        lines.append("Current workflow integration inspection:\n" + json.dumps({
            "issues": inspection.get("issues", []),
            "warnings": inspection.get("warnings", []),
            "details": inspection.get("details", {}),
        }, ensure_ascii=False, indent=2))
    if install.get("installed"):
        lines.append("Installed WhatDreamsCost status: detected. Registered nodes: " + ", ".join(install.get("registered_nodes", [])))
    else:
        lines.append("Installed WhatDreamsCost status: not detected in this runtime. Planning/explanation can continue, but do not claim its workflows are executable until the pack and required dependencies are present.")
    return "\n".join(lines)
