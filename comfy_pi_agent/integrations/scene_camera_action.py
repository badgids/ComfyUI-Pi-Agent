from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from ..compat import get_live_node_registry
from ..io_utils import load_json

SCA_NODE_IDS = {"SceneNode", "ActingNode", "DirectingNode"}
SCA_PACK_NAMES = (
    "ComfyUI-scene-camera-action",
    "comfyui-scene-camera-action",
    "scene-camera-action",
)


def _profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "integrations" / "scene_camera_action.json"


def load_scene_camera_action_profile() -> dict[str, Any]:
    return json.loads(_profile_path().read_text(encoding="utf-8"))


def _candidate_custom_node_roots() -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("COMFYUI_SCENE_CAMERA_ACTION_PATH", "").strip()
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
        and (path / "nodes.py").is_file()
        and (path / "presets").is_dir()
        and (path / "skills" / "scene-staging-builder" / "SKILL.md").is_file()
    )


def find_scene_camera_action_install() -> dict[str, Any]:
    registry = get_live_node_registry()
    registered = sorted(SCA_NODE_IDS.intersection(registry.keys()))
    candidates: list[Path] = []

    explicit = os.environ.get("COMFYUI_SCENE_CAMERA_ACTION_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    for root in _candidate_custom_node_roots():
        if _looks_like_pack(root):
            candidates.append(root)
        if root.is_dir():
            for name in SCA_PACK_NAMES:
                candidates.append(root / name)
            try:
                for child in root.iterdir():
                    low = child.name.lower()
                    if child.is_dir() and "scene" in low and "camera" in low and "action" in low:
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

    presets: list[str] = []
    upstream_skill: str | None = None
    if install is not None:
        try:
            presets = sorted(str(p) for p in (install / "presets").glob("*.json") if p.is_file())
        except Exception:
            presets = []
        candidate_skill = install / "skills" / "scene-staging-builder" / "SKILL.md"
        if candidate_skill.is_file():
            upstream_skill = str(candidate_skill)

    return {
        "integration": "scene-camera-action",
        "installed": bool(install or registered),
        "install_path": str(install) if install else None,
        "registered_nodes": registered,
        "all_known_nodes_registered": SCA_NODE_IDS.issubset(set(registry.keys())) if registry else False,
        "preset_files": presets,
        "upstream_skill_path": upstream_skill,
        "source_repository": "https://github.com/arturitu/ComfyUI-scene-camera-action",
        "node_pack_license": "MIT",
        "upstream_skill_license": "Apache-2.0",
        "interoperability_note": (
            "ComfyUI-Pi does not vendor the upstream implementation. It recognizes the public node IDs, "
            "uses live ComfyUI schemas, and applies original lazily loaded guidance derived from the pack's public documentation and skill contract."
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


def detect_scene_camera_action(workflow: Any = None, message: str = "") -> bool:
    if SCA_NODE_IDS.intersection(_workflow_node_types(workflow)):
        return True
    text = str(message or "").lower()
    terms = (
        "scene camera action", "scene-camera-action", "comfyui-scene-camera-action",
        "staging 3d", "staging 3d node", "acting 3d", "acting 3d node",
        "directing 3d", "directing 3d node", "scenenode", "actingnode", "directingnode",
        "scene staging builder", "3d previz", "3d pre-viz", "previz scene",
    )
    return any(term in text for term in terms)


def _ui_nodes(data: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [n for n in data.get("nodes", []) if isinstance(n, dict) and str(n.get("type")) == node_type]


def _ui_links(data: dict[str, Any]) -> list[list[Any]]:
    return [link for link in data.get("links", []) if isinstance(link, list) and len(link) >= 5]


def _connected(data: dict[str, Any], source_type: str, target_type: str) -> bool:
    nodes = {str(n.get("id")): str(n.get("type")) for n in data.get("nodes", []) if isinstance(n, dict)}
    for link in _ui_links(data):
        if nodes.get(str(link[1])) == source_type and nodes.get(str(link[3])) == target_type:
            return True
    return False


def _parse_scene_state(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def inspect_scene_state(scene: Any) -> dict[str, Any]:
    data = _parse_scene_state(scene)
    issues: list[str] = []
    warnings: list[str] = []
    if not data:
        return {"valid": False, "issues": ["SceneState is empty or not valid JSON."], "warnings": [], "summary": {}}
    if data.get("type") != "cube_scene":
        issues.append("SceneState type should be 'cube_scene'.")
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        issues.append("SceneState nodes must be an array.")
        nodes = []

    ids: set[str] = set()
    block_count = 0
    group_count = 0

    def walk(items: list[Any], parent_offset_y: float = 0.0) -> None:
        nonlocal block_count, group_count
        for item in items:
            if not isinstance(item, dict):
                issues.append("SceneState contains a non-object node.")
                continue
            node_id = str(item.get("id") or "")
            if not node_id:
                issues.append("A scene node is missing an id.")
            elif node_id in ids:
                issues.append(f"Duplicate scene node id: {node_id}")
            else:
                ids.add(node_id)
            kind = str(item.get("type") or "")
            transform = item.get("transform") if isinstance(item.get("transform"), dict) else {}
            if kind == "block":
                block_count += 1
                required = ("px", "py", "pz", "rx", "ry", "rz", "sx", "sy", "sz")
                for key in required:
                    if not isinstance(transform.get(key), (int, float)):
                        issues.append(f"Block {node_id or '<unknown>'} has invalid/missing transform value: {key}.")
                # Only flag obvious below-ground blocks; rotated/elevated blocks cannot be judged with py=sy/2 alone.
                if isinstance(transform.get("py"), (int, float)) and isinstance(transform.get("sy"), (int, float)):
                    if float(transform["py"]) + float(transform["sy"]) / 2.0 < -0.001:
                        warnings.append(f"Block {node_id or '<unknown>'} extends entirely below Y=0.")
            elif kind == "group":
                group_count += 1
                children = item.get("children")
                if not isinstance(children, list):
                    issues.append(f"Group {node_id or '<unknown>'} must contain a children array.")
                else:
                    walk(children, parent_offset_y + float(transform.get("py", 0) or 0))
            else:
                issues.append(f"Unsupported scene node type '{kind}' in {node_id or '<unknown>'}; current staging skill uses block/group nodes.")

    walk(nodes)
    spawn = data.get("spawn_point")
    if spawn is not None:
        if not isinstance(spawn, dict):
            issues.append("spawn_point must be an object when present.")
        else:
            for key in ("px", "py", "pz", "ry"):
                if not isinstance(spawn.get(key), (int, float)):
                    issues.append(f"spawn_point.{key} must be numeric.")

    if isinstance(data.get("num_assets"), int) and data.get("num_assets") != len(nodes):
        warnings.append("num_assets does not match the number of top-level scene nodes; the frontend may recalculate it.")

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "top_level_nodes": len(nodes),
            "block_count": block_count,
            "group_count": group_count,
            "has_spawn_point": isinstance(spawn, dict),
        },
    }


def inspect_scene_camera_action_workflow(workflow: Any) -> dict[str, Any]:
    data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    if not isinstance(data, dict):
        return {"detected": False, "issues": ["Workflow is not a JSON object."], "warnings": [], "recommendations": []}

    node_types = _workflow_node_types(data)
    present = sorted(SCA_NODE_IDS.intersection(node_types))
    if not present:
        return {
            "detected": False,
            "node_types": node_types,
            "issues": [],
            "warnings": [],
            "recommendations": ["No Scene Camera Action nodes were found."],
            "profile": load_scene_camera_action_profile(),
        }

    issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"present_nodes": present}

    if isinstance(data.get("nodes"), list):
        if "ActingNode" in present and "SceneNode" in present and not _connected(data, "SceneNode", "ActingNode"):
            warnings.append("SceneNode and ActingNode are both present but are not connected Scene → Acting.")
        if "DirectingNode" in present and "ActingNode" in present and not _connected(data, "ActingNode", "DirectingNode"):
            warnings.append("ActingNode and DirectingNode are both present but are not connected Acting → Directing.")
        if "ActingNode" in present and "SceneNode" not in present:
            warnings.append("ActingNode has no SceneNode in this graph. Its scene input is optional, but a staged environment is normally expected for previz.")
        if "DirectingNode" in present and "ActingNode" not in present:
            warnings.append("DirectingNode has no ActingNode in this graph. Its acting input is optional, but camera previz normally consumes acting data.")

        scene_reports = []
        for node in _ui_nodes(data, "SceneNode"):
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            scene_value = props.get("scene_data")
            # UI frontends may keep scene state outside properties/widgets. Do not guess widget indices.
            if scene_value:
                scene_reports.append(inspect_scene_state(scene_value))
        if scene_reports:
            details["scene_state_reports"] = scene_reports
    else:
        # API graphs expose named inputs and are safer to inspect directly.
        scene_reports = []
        for node in data.values():
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type") or "")
            inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
            if class_type == "SceneNode" and "scene_data" in inputs:
                scene_reports.append(inspect_scene_state(inputs.get("scene_data")))
            if class_type == "ActingNode":
                actor_type = inputs.get("actor_type")
                if actor_type not in (None, "human", "car"):
                    issues.append(f"ActingNode actor_type '{actor_type}' is not one of human/car.")
            if class_type == "ActingNode" and isinstance(inputs.get("duration"), (int, float)):
                if not 4.0 <= float(inputs["duration"]) <= 15.0:
                    warnings.append("ActingNode duration is outside the upstream UI's documented 4–15 second control range.")
        if scene_reports:
            details["scene_state_reports"] = scene_reports

    recommendations.extend([
        "Use the installed pack's live /object_info schemas as the final authority for sockets and widget behavior.",
        "Use SceneNode for environment/blockout, ActingNode for human/car movement recording, and DirectingNode for camera-cut previz output.",
        "For generated SceneState presets, use block/group primitives, keep the built-in floor implicit, preserve ground alignment, and include an actor-aware spawn_point when useful.",
        "Do not invent frontend recording/directing state. Let the Acting and Directing widgets create motion_data/directing_data interactively unless the installed schema provides a validated structured edit path.",
        "Preserve original presets/workflows before nontrivial edits and validate the resulting JSON and live node graph.",
    ])

    return {
        "detected": True,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "details": details,
        "profile": load_scene_camera_action_profile(),
        "installation": find_scene_camera_action_install(),
    }


def create_scene_camera_action_plan(
    request: str,
    actor_type: str = "human",
    duration_seconds: float = 7.0,
    include_directing: bool = True,
    scene_source: str = "generated",
) -> dict[str, Any]:
    actor = str(actor_type or "human").lower()
    if actor not in {"human", "car"}:
        actor = "human"
    duration = max(4.0, min(15.0, float(duration_seconds)))
    source = str(scene_source or "generated").lower()
    if source not in {"generated", "preset", "existing"}:
        source = "generated"
    stages = ["staging", "acting"] + (["directing"] if include_directing else [])
    return {
        "schema_version": "1.0",
        "integration": "scene-camera-action",
        "request": request,
        "actor_type": actor,
        "duration_seconds": duration,
        "scene_source": source,
        "stages": stages,
        "required_pack_nodes": ["SceneNode", "ActingNode"] + (["DirectingNode"] if include_directing else []),
        "scene_rules": load_scene_camera_action_profile().get("scene_state_rules", []),
        "installation": find_scene_camera_action_install(),
        "status": "planned",
    }


def _base_ui_workflow(plan: dict[str, Any]) -> dict[str, Any]:
    # This graph uses only the pack's simple public socket contract. Interactive scene/motion/camera
    # state is deliberately left blank so the upstream frontend remains the authority.
    nodes: list[dict[str, Any]] = [
        {
            "id": 1, "type": "SceneNode", "pos": [0, 0], "size": [360, 260], "flags": {}, "order": 0, "mode": 0,
            "inputs": [],
            "outputs": [{"name": "scene_data", "type": "SCENE", "links": [1]}],
            "properties": {"Node name for S&R": "SceneNode"},
            "widgets_values": [""],
        },
        {
            "id": 2, "type": "ActingNode", "pos": [460, 0], "size": [420, 320], "flags": {}, "order": 1, "mode": 0,
            "inputs": [{"name": "scene", "type": "SCENE", "link": 1}],
            "outputs": [{"name": "acting_data", "type": "ACTING", "links": [2] if "directing" in plan["stages"] else []}],
            "properties": {"Node name for S&R": "ActingNode"},
            "widgets_values": [plan["actor_type"], 10.0, plan["duration_seconds"], ""],
        },
    ]
    links: list[list[Any]] = [[1, 1, 0, 2, 0, "SCENE"]]
    last_link = 1
    last_node = 2
    if "directing" in plan["stages"]:
        nodes.append({
            "id": 3, "type": "DirectingNode", "pos": [980, 0], "size": [480, 360], "flags": {}, "order": 2, "mode": 0,
            "inputs": [{"name": "acting", "type": "ACTING", "link": 2}],
            "outputs": [
                {"name": "captured_video", "type": "VIDEO", "links": []},
                {"name": "captured_stage", "type": "IMAGE", "links": []},
            ],
            "properties": {"Node name for S&R": "DirectingNode"},
            "widgets_values": [""],
        })
        links.append([2, 2, 0, 3, 0, "ACTING"])
        last_link = 2
        last_node = 3
    return {
        "last_node_id": last_node,
        "last_link_id": last_link,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {
            "comfyui_pi_agent": {
                "integration": "scene-camera-action",
                "request": plan["request"],
                "note": "The base chain is created from public node schemas. Use the installed Scene/Acting/Directing widgets for interactive frontend-managed scene, motion, and camera state.",
            }
        },
        "version": 0.4,
    }


def create_scene_camera_action_workflow(
    request: str,
    actor_type: str = "human",
    duration_seconds: float = 7.0,
    include_directing: bool = True,
    scene_source: str = "generated",
) -> dict[str, Any]:
    plan = create_scene_camera_action_plan(request, actor_type, duration_seconds, include_directing, scene_source)
    workflow = _base_ui_workflow(plan)
    return {
        "ok": True,
        "runnable": bool(plan["installation"].get("installed")),
        "workflow": copy.deepcopy(workflow),
        "source_workflow": "ComfyUI-Pi public-schema base chain",
        "plan": plan,
        "inspection": inspect_scene_camera_action_workflow(workflow),
        "editing_policy": {
            "safe": [
                "Edit SceneState JSON using stable block/group transforms and validate it before loading.",
                "Use live /object_info schemas for node/socket edits.",
                "Use the upstream widgets for recorded motion and camera-cut timeline state.",
            ],
            "avoid": [
                "Do not fabricate recorded motion_data or directing_data from guessed frontend serialization.",
                "Do not add a floor block; the staging viewport already provides the floor at Y=0.",
                "Do not place ground-resting blocks with their center at Y=0; account for half-height.",
            ],
        },
    }


def build_scene_camera_action_context(workflow: Any = None, message: str = "") -> str:
    if not detect_scene_camera_action(workflow, message):
        return ""
    profile = load_scene_camera_action_profile()
    install = find_scene_camera_action_install()
    text = str(message or "").lower()
    present = set(_workflow_node_types(workflow))

    def wants(*terms: str, nodes: tuple[str, ...] = ()) -> bool:
        return any(term in text for term in terms) or bool(present.intersection(nodes))

    lines = [
        "Dynamically loaded integration knowledge: ComfyUI-scene-camera-action",
        f"Source node pack: {profile['source_repository']} (node pack MIT; upstream scene-staging-builder skill Apache-2.0).",
        "Public node IDs: SceneNode (Staging 3D Node), ActingNode (Acting 3D Node), DirectingNode (Directing 3D Node).",
        "Runtime authority: use installed live /object_info schemas and the pack's own frontend behavior. Never guess serialized interactive state.",
    ]

    if wants("scene", "staging", "previz", "pre-viz", "preset", "build", "create", "edit", nodes=("SceneNode",)):
        lines.extend([
            "SceneNode consumes/produces SceneState JSON. The upstream staging skill builds scenes from block/group box primitives; the viewport already has a floor, so do not add a floor/ground slab merely to represent Y=0.",
            "SceneState creation contract: root type=cube_scene with nodes[]. Blocks/groups have stable id, type, name, and transform {px,py,pz,rx,ry,rz,sx,sy,sz}; groups store child scene nodes in children[]. num_assets and spawn_point are root metadata when used.",
            "Coordinate system: X left/right, Y vertical with ground at 0, Z depth. A non-rotated ground-resting block of height sy normally centers at py=sy/2. Keep generated staging within the pack's documented 100x100m world bounds unless live behavior proves otherwise.",
            "Use logical group nodes for compound objects. Include spawn_point {px,py,pz,ry} when actor placement matters; if spawning on an elevated surface, put py at the supporting surface top rather than inside the block.",
            "For edits: parse existing SceneState, target ids/names, apply the smallest transform/add/delete delta, then revalidate ids, numeric transforms, ground/clearance rules, and JSON.",
            "Car-aware staging: roads should have practical vehicle clearance; human-aware staging: preserve realistic doorway/stair clearances. Exact artistic geometry remains user/project specific.",
        ])
    if wants("acting", "actor", "human", "car", "motion", nodes=("ActingNode",)):
        lines.extend([
            "ActingNode accepts Scene data, actor_type human/car, actor_speed, duration, and frontend-managed motion_data; it outputs ACTING data. The documented interactive duration range is 4–15 seconds.",
            "Do not invent recorded motion_data unless a validated live schema/editor path exists. Let the upstream acting widget record WASD/arrow-key motion and preserve the selected spawn point/scene scale.",
        ])
    if wants("directing", "camera", "cut", "tpv", "fpv", "wide", "side", nodes=("DirectingNode",)):
        lines.extend([
            "DirectingNode consumes ACTING data plus frontend-managed directing_data and outputs Captured Video (VIDEO) plus Captured Stage (IMAGE). The upstream UI supports camera-cut previz including TPV, FPV, Wide, and Side modes.",
            "Treat directing_data as frontend-managed camera timeline state; do not guess its serialization. Use the resulting video/stage image as previz/reference media for downstream V2V/I2V/video-generation workflows.",
        ])
    if wants("skill", "scene staging builder", "natural language", "reference image"):
        lines.append("The upstream scene-staging-builder skill is a spatial-reasoning contract for generating SceneState presets from text/reference images. ComfyUI-Pi carries an original compact operating procedure and loads its full internal guide only for explicit deep/tutorial requests, preserving sparse context.")

    if workflow not in (None, "", {}):
        inspection = inspect_scene_camera_action_workflow(workflow)
        lines.append("Current workflow integration inspection:\n" + json.dumps({
            "issues": inspection.get("issues", []),
            "warnings": inspection.get("warnings", []),
            "details": inspection.get("details", {}),
        }, ensure_ascii=False, indent=2))
    if install.get("installed"):
        lines.append("Installed Scene Camera Action status: detected. Registered nodes: " + ", ".join(install.get("registered_nodes", [])))
    else:
        lines.append("Installed Scene Camera Action status: not detected. Planning, SceneState authoring, and explanation can continue, but do not claim the interactive workflow is runnable until the pack is installed.")
    return "\n".join(lines)
