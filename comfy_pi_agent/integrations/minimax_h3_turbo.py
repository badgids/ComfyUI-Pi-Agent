from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from ..compat import get_live_node_registry
from ..io_utils import load_json

TURBO_NODE_IDS = {"MiniMaxH3TurboLoRA", "MiniMaxH3TurboSampler"}
TURBO_PACK_NAMES = (
    "ComfyUI-MiniMax-H3-Turbo",
    "comfyui-minimax-h3-turbo",
    "MiniMax-H3-Turbo",
)


def _profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "integrations" / "minimax_h3_turbo.json"


def load_minimax_h3_turbo_profile() -> dict[str, Any]:
    return json.loads(_profile_path().read_text(encoding="utf-8"))


def _candidate_custom_node_roots() -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("COMFYUI_MINIMAX_H3_TURBO_PATH", "").strip()
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
        and (path / "__init__.py").is_file()
        and (path / "h3_silu_temb_grid.safetensors").is_file()
        and (path / "example_workflows").is_dir()
    )


def find_minimax_h3_turbo_install() -> dict[str, Any]:
    registry = get_live_node_registry()
    registered = sorted(TURBO_NODE_IDS.intersection(registry.keys()))
    candidates: list[Path] = []
    explicit = os.environ.get("COMFYUI_MINIMAX_H3_TURBO_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    for root in _candidate_custom_node_roots():
        if _looks_like_pack(root):
            candidates.append(root)
        if root.is_dir():
            for name in TURBO_PACK_NAMES:
                candidates.append(root / name)
            try:
                for child in root.iterdir():
                    low = child.name.lower()
                    if child.is_dir() and "minimax" in low and "h3" in low and "turbo" in low:
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
        "integration": "minimax-h3-turbo",
        "installed": bool(install or registered),
        "install_path": str(install) if install else None,
        "registered_nodes": registered,
        "all_known_nodes_registered": TURBO_NODE_IDS.issubset(set(registry.keys())) if registry else False,
        "example_workflows": examples,
        "source_repository": "https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo",
        "license": "Apache-2.0",
        "interoperability_note": (
            "ComfyUI-Pi does not copy the Turbo node implementation or weights. It interoperates with an installed copy through public node IDs, live schemas, and the pack's own example workflow."
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


def detect_minimax_h3_turbo(workflow: Any = None, message: str = "") -> bool:
    if TURBO_NODE_IDS.intersection(_workflow_node_types(workflow)):
        return True
    text = str(message or "").lower()
    terms = (
        "minimax h3 turbo", "minimax-h3 turbo", "minimax-h3-turbo",
        "h3 turbo", "h3turbo", "minimaxh3turbo", "minimaxh3turbolora",
        "minimaxh3turbosampler", "turbo lora", "turbo sampler (4-step)",
    )
    return any(term in text for term in terms)


def _ui_nodes(data: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [n for n in data.get("nodes", []) if isinstance(n, dict) and str(n.get("type")) == node_type]


def _links(data: dict[str, Any]) -> list[list[Any]]:
    return [link for link in data.get("links", []) if isinstance(link, list) and len(link) >= 5]


def _node_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(n.get("id")): n for n in data.get("nodes", []) if isinstance(n, dict) and n.get("id") is not None}


def _link_source_type(data: dict[str, Any], target_node: dict[str, Any], input_name: str) -> str | None:
    nodes = _node_map(data)
    target_id = str(target_node.get("id"))
    inputs = target_node.get("inputs") if isinstance(target_node.get("inputs"), list) else []
    target_slot = None
    for index, item in enumerate(inputs):
        if isinstance(item, dict) and item.get("name") == input_name:
            target_slot = index
            break
    if target_slot is None:
        return None
    for link in _links(data):
        if str(link[3]) == target_id and int(link[4]) == target_slot:
            source = nodes.get(str(link[1]))
            return str(source.get("type")) if source else None
    return None


def inspect_minimax_h3_turbo_workflow(workflow: Any) -> dict[str, Any]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return {"detected": False, "issues": ["Workflow is not a JSON object."], "warnings": [], "recommendations": []}

    node_types = _workflow_node_types(data)
    present = sorted(TURBO_NODE_IDS.intersection(node_types))
    if not present:
        return {
            "detected": False,
            "node_types": node_types,
            "issues": [],
            "warnings": [],
            "recommendations": ["No MiniMax H3 Turbo nodes were found."],
            "profile": load_minimax_h3_turbo_profile(),
        }

    issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"present_nodes": present}

    if "MiniMaxH3TurboLoRA" not in present:
        issues.append("MiniMaxH3TurboSampler is present without MiniMaxH3TurboLoRA. The 4-step sampler is intended for the Turbo LoRA path.")
    if "MiniMaxH3TurboSampler" not in present:
        issues.append("MiniMaxH3TurboLoRA is present without MiniMaxH3TurboSampler. At 4 steps, the stock sampler can over-step the audio stream; use the pack's dual-schedule Turbo sampler.")

    if isinstance(data.get("nodes"), list):
        schedulers = _ui_nodes(data, "BasicScheduler")
        scheduler_strings = [str(v).lower() for n in schedulers for v in (n.get("widgets_values") or []) if isinstance(v, str)]
        scheduler_numbers = [v for n in schedulers for v in (n.get("widgets_values") or []) if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if schedulers and "simple" not in scheduler_strings:
            warnings.append("A BasicScheduler was found but 'simple' was not visible in its widget values. The Turbo starting profile uses scheduler=simple.")
        if schedulers and not any(float(v) == 4.0 for v in scheduler_numbers):
            warnings.append("A BasicScheduler was found but a visible 4-step value was not detected. The Turbo LoRA is designed around a 4-step starting profile; values >=4 are supported upstream.")

        samplers = _ui_nodes(data, "SamplerCustomAdvanced")
        if samplers:
            for sampler in samplers:
                source = _link_source_type(data, sampler, "sampler")
                if source and source != "MiniMaxH3TurboSampler":
                    issues.append(f"SamplerCustomAdvanced sampler input is fed by {source}, not MiniMaxH3TurboSampler.")

        guiders = _ui_nodes(data, "BasicGuider")
        if guiders:
            model_sources = {_link_source_type(data, node, "model") for node in guiders}
            if model_sources and "MiniMaxH3TurboLoRA" not in model_sources:
                warnings.append("BasicGuider model input does not visibly come directly from MiniMaxH3TurboLoRA. Validate the model path before running.")

        unets = _ui_nodes(data, "UNETLoader")
        filenames = [str(v) for n in unets for v in (n.get("widgets_values") or []) if isinstance(v, str)]
        if filenames and not any("minimax_h3" in v.lower() for v in filenames):
            warnings.append("The visible diffusion-model filename does not look like a MiniMax H3 base. Validate the installed model before using the Turbo LoRA.")

        clips = _ui_nodes(data, "CLIPLoader")
        if clips and not any("minimax" in [str(v).lower() for v in (n.get("widgets_values") or [])] for n in clips):
            warnings.append("No CLIPLoader visibly configured with type 'minimax' was detected.")

        lora_nodes = _ui_nodes(data, "MiniMaxH3TurboLoRA")
        details["lora_widgets"] = [n.get("widgets_values", []) for n in lora_nodes]
        details["has_joint_av_latent_node"] = any(t in node_types for t in ("EmptyMiniMaxH3LatentAV", "MiniMaxH3ImageToVideo"))
    else:
        # API graph: inspect named inputs without guessing UI widget positions.
        for node in data.values():
            if not isinstance(node, dict):
                continue
            ctype = str(node.get("class_type") or "")
            inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
            if ctype == "MiniMaxH3TurboLoRA":
                strength = inputs.get("strength")
                if isinstance(strength, (int, float)) and (strength < -10 or strength > 10):
                    issues.append("MiniMaxH3TurboLoRA strength is outside the node's documented -10..10 input range.")
            if ctype == "BasicScheduler":
                if inputs.get("scheduler") not in (None, "simple"):
                    warnings.append("BasicScheduler scheduler is not 'simple'; Turbo's documented starting profile uses simple.")
                if isinstance(inputs.get("steps"), (int, float)) and float(inputs["steps"]) < 4:
                    issues.append("Turbo scheduler steps are below 4; the upstream node documents >=4 as valid.")

    recommendations.extend([
        "Start from the installed pack's current example workflow, or the current official MiniMax H3 T2V/I2V workflow plus the two Turbo substitutions.",
        "Insert MiniMaxH3TurboLoRA in the MODEL path after the H3 diffusion loader and before the guider/sampling path.",
        "Feed MiniMaxH3TurboSampler into SamplerCustomAdvanced and use BasicScheduler with scheduler=simple and a 4-step starting profile.",
        "Keep MiniMax H3 conditioning, joint video/audio latent, video/audio VAE decode, and CreateVideo muxing otherwise equivalent to the validated official workflow.",
        "Use LoRA strength to trade smear/ghosting versus over-sharp grain; default 1.0 is the upstream starting value.",
        "Use low_vram only when memory pressure requires it: upstream v1.2.2 documents bypass/off as sharper and merge/on as lower-VRAM but softer on quantized bases.",
        "MiniMax H3 lengths remain 24 fps and follow the model's 17k+5 frame grid; do not treat Turbo as changing the model's temporal constraints.",
    ])

    return {
        "detected": True,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "details": details,
        "profile": load_minimax_h3_turbo_profile(),
        "installation": find_minimax_h3_turbo_install(),
    }


def create_minimax_h3_turbo_plan(
    request: str,
    mode: str = "t2v",
    steps: int = 4,
    lora_strength: float = 1.0,
    low_vram: bool = False,
) -> dict[str, Any]:
    mode = str(mode or "t2v").lower()
    if mode not in {"t2v", "i2v", "flf"}:
        mode = "t2v"
    steps = max(4, int(steps))
    strength = max(-10.0, min(10.0, float(lora_strength)))
    warnings: list[str] = []
    if steps > 4:
        warnings.append("The current Turbo checkpoint is designed to be sharp at 4 steps; more steps are allowed but cost more time.")
    if low_vram:
        warnings.append("low_vram merges the LoRA for lower peak VRAM but can be softer on quantized bases; use it primarily when the bypass path OOMs.")
    return {
        "schema_version": "1.0",
        "integration": "minimax-h3-turbo",
        "request": request,
        "mode": mode,
        "steps": steps,
        "scheduler": "simple",
        "lora_strength": strength,
        "low_vram": bool(low_vram),
        "required_pack_nodes": ["MiniMaxH3TurboLoRA", "MiniMaxH3TurboSampler"],
        "workflow_rules": load_minimax_h3_turbo_profile().get("workflow_rules", []),
        "installation": find_minimax_h3_turbo_install(),
        "warnings": warnings,
        "status": "planned",
    }


def _pick_example(install: dict[str, Any]) -> Path | None:
    examples = [Path(p) for p in install.get("example_workflows", [])]
    for path in examples:
        if "minimax_h3_t2v_turbo" in path.name.lower():
            return path
    return examples[0] if examples else None


def _attach_image_input(workflow: dict[str, Any], use_last_frame: bool = False) -> tuple[dict[str, Any], str | None]:
    nodes = workflow.get("nodes") if isinstance(workflow.get("nodes"), list) else []
    target = next((n for n in nodes if isinstance(n, dict) and n.get("type") == "MiniMaxH3ImageToVideo"), None)
    if target is None:
        return workflow, "The upstream example has no MiniMaxH3ImageToVideo node to receive an image reference."
    inputs = target.get("inputs") if isinstance(target.get("inputs"), list) else []
    desired = "last_frame" if use_last_frame else "first_frame"
    slot = next((i for i, item in enumerate(inputs) if isinstance(item, dict) and item.get("name") == desired), None)
    if slot is None:
        return workflow, f"The installed example does not expose a {desired} input; use live schemas instead of guessing."
    # Do not override an existing connection.
    if isinstance(inputs[slot], dict) and inputs[slot].get("link") is not None:
        return workflow, None

    max_node = max([int(n.get("id")) for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), int)] or [0])
    links = workflow.get("links") if isinstance(workflow.get("links"), list) else []
    max_link = max([int(l[0]) for l in links if isinstance(l, list) and l and isinstance(l[0], int)] or [0])
    new_node_id = max_node + 1
    new_link_id = max_link + 1
    load = {
        "id": new_node_id,
        "type": "LoadImage",
        "pos": [float(target.get("pos", [0, 0])[0]) - 460, float(target.get("pos", [0, 0])[1]) + (260 if use_last_frame else 120)],
        "size": [320, 310], "flags": {}, "order": 0, "mode": 0,
        "inputs": [],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [new_link_id]},
            {"name": "MASK", "type": "MASK", "links": []},
        ],
        "properties": {"Node name for S&R": "LoadImage"},
        "widgets_values": ["example.png", "image"],
    }
    nodes.append(load)
    inputs[slot]["link"] = new_link_id
    links.append([new_link_id, new_node_id, 0, target.get("id"), slot, "IMAGE"])
    workflow["last_node_id"] = max(int(workflow.get("last_node_id", 0) or 0), new_node_id)
    workflow["last_link_id"] = max(int(workflow.get("last_link_id", 0) or 0), new_link_id)
    return workflow, None


def create_minimax_h3_turbo_workflow(
    request: str,
    mode: str = "t2v",
    steps: int = 4,
    lora_strength: float = 1.0,
    low_vram: bool = False,
) -> dict[str, Any]:
    plan = create_minimax_h3_turbo_plan(request, mode, steps, lora_strength, low_vram)
    install = plan["installation"]
    example = _pick_example(install)
    if example is None or not example.is_file():
        return {
            "ok": False,
            "runnable": False,
            "workflow": None,
            "source_workflow": None,
            "plan": plan,
            "error": "MiniMax H3 Turbo is not installed with its example workflow. ComfyUI-Pi will not fabricate the full upstream H3 graph without a validated baseline.",
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
    warnings = list(plan.get("warnings", []))
    if plan["mode"] in {"i2v", "flf"}:
        workflow, warning = _attach_image_input(workflow, use_last_frame=False)
        if warning:
            warnings.append(warning)
        else:
            warnings.append("Replace the generated example.png first-frame placeholder with the user's actual source image before execution.")
    if plan["mode"] == "flf":
        workflow, warning = _attach_image_input(workflow, use_last_frame=True)
        if warning:
            warnings.append(warning)
        else:
            warnings.append("Replace the generated example.png last-frame placeholder with the user's actual last-frame image before execution.")

    extra = workflow.setdefault("extra", {})
    if isinstance(extra, dict):
        extra["comfyui_pi_agent"] = {
            "integration": "minimax-h3-turbo",
            "request": request,
            "plan": {
                "mode": plan["mode"],
                "steps": plan["steps"],
                "scheduler": plan["scheduler"],
                "lora_strength": plan["lora_strength"],
                "low_vram": plan["low_vram"],
            },
            "note": "Created from the installed MiniMax H3 Turbo pack's current example workflow. Validate current live schemas before changing Turbo LoRA widget serialization.",
        }

    return {
        "ok": True,
        "runnable": bool(install.get("installed")),
        "workflow": workflow,
        "source_workflow": str(example),
        "plan": {**plan, "warnings": warnings},
        "inspection": inspect_minimax_h3_turbo_workflow(workflow),
        "editing_policy": {
            "safe": [
                "Use live ComfyUI schemas for normal sockets and node inputs.",
                "Preserve the stock H3 conditioning/AV decode structure and substitute only the Turbo model/sampler path unless the task requires more.",
                "Use the installed example workflow as the baseline and preserve originals before edits.",
            ],
            "avoid": [
                "Do not use a stock single-schedule sampler at 4 steps and claim joint audio is validated.",
                "Do not assume low_vram is a quality-neutral switch on quantized bases.",
                "Do not guess LoRA widget indexes when the installed live schema can be queried.",
            ],
        },
    }


def build_minimax_h3_turbo_context(workflow: Any = None, message: str = "") -> str:
    if not detect_minimax_h3_turbo(workflow, message):
        return ""
    profile = load_minimax_h3_turbo_profile()
    install = find_minimax_h3_turbo_install()
    text = str(message or "").lower()
    present = set(_workflow_node_types(workflow))

    def wants(*terms: str, nodes: tuple[str, ...] = ()) -> bool:
        return any(term in text for term in terms) or bool(present.intersection(nodes))

    lines = [
        "Dynamically loaded integration knowledge: ComfyUI-MiniMax-H3-Turbo",
        f"Source node pack: {profile['source_repository']} (Apache-2.0). Reviewed upstream v1.2.2.",
        "Public node IDs: MiniMaxH3TurboLoRA (MODEL→MODEL) and MiniMaxH3TurboSampler (→SAMPLER).",
        "Runtime authority: installed live /object_info schemas and the pack's installed example workflow override this static profile when versions differ.",
        "Turbo modifies the normal MiniMax H3 graph; it does not replace H3 conditioning, joint video/audio latent handling, video/audio VAE decode, or final muxing.",
    ]
    if wants("turbo", "4 step", "4-step", "sampler", "workflow", "create", "edit", "repair", nodes=("MiniMaxH3TurboSampler", "MiniMaxH3TurboLoRA")):
        lines.extend([
            "Required substitutions: insert MiniMaxH3TurboLoRA after the H3 diffusion model loader in the MODEL path; feed MiniMaxH3TurboSampler into SamplerCustomAdvanced; use BasicScheduler scheduler=simple with 4 steps as the starting profile.",
            "Why the custom sampler matters: H3 video and audio use different flow schedules (upstream Turbo code uses video shift 12 and audio shift 3). A stock single-schedule sampler can over-step audio at four steps and produce broken/distorted audio.",
            "The Turbo LoRA supports full bf16/int8_convrot and pruned/curve variants including pruned int8/fp8 according to upstream v1.2.2; the node handles pruned time-conditioning reinjection internally.",
            "LoRA strength default is 1.0. If output smears/ghosts, upstream suggests nudging strength upward; if it becomes over-sharp/grainy, nudge downward. Validate visually rather than hardcoding a universal value.",
            "low_vram OFF is the sharper runtime-bypass path but uses more peak VRAM. low_vram ON merges the LoRA for lower peak VRAM and may be softer on quantized bases. Turn it on primarily when memory pressure requires it.",
            "Frame rate/shape constraints remain MiniMax H3 constraints: 24 fps, width/height multiples of 32, and lengths on the 17k+5 frame grid (about 124 frames ≈ 5 s). Turbo does not remove those constraints.",
            "For creation, prefer the installed pack's current example workflow. For I2V/FLF, preserve the same Turbo model/sampler path and use the current MiniMaxH3ImageToVideo first/last-frame inputs validated from live schemas.",
        ])
    if wants("director", "minimax h3 director"):
        lines.append("Do not assume MiniMax H3 Turbo and MiniMax H3 Director are automatically compatible just because both target H3. Validate the actual Director sampling/model path and live schemas before combining them; keep each integration's guidance separate until a combined workflow is proven.")

    if workflow not in (None, "", {}):
        inspection = inspect_minimax_h3_turbo_workflow(workflow)
        lines.append("Current workflow integration inspection:\n" + json.dumps({
            "issues": inspection.get("issues", []),
            "warnings": inspection.get("warnings", []),
            "details": inspection.get("details", {}),
        }, ensure_ascii=False, indent=2))
    if install.get("installed"):
        lines.append("Installed MiniMax H3 Turbo status: detected. Registered nodes: " + ", ".join(install.get("registered_nodes", [])))
    else:
        lines.append("Installed MiniMax H3 Turbo status: not detected. Planning/explanation can continue, but do not claim Turbo workflows are runnable until the pack, LoRA, and base H3 components are present.")
    return "\n".join(lines)
