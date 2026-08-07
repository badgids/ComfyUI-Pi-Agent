from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .compat import get_live_node_registry
from .docx_writer import write_docx
from .io_utils import atomic_write_json, atomic_write_text, resolve_output_root, safe_join, slugify
from .models import inventory_models
from .workflow import analyze_workflow, load_workflow_collection, validate_workflow


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stage_markdown(stage: dict[str, Any]) -> str:
    required_nodes = "\n".join(f"- `{name}`" for name in stage["required_custom_nodes"]) or "- No custom node classes were detected."
    models = "\n".join(f"- `{name}`" for name in stage["required_models"]) or "- No model filename was detected directly in the workflow."
    inputs = "\n".join(f"- `{name}`" for name in stage["required_inputs"]) or "- Follow the workflow input nodes and canvas notes."
    issues = stage.get("issues", [])
    issue_text = "\n".join(f"- **{i['severity'].upper()}**: {i['message']}" for i in issues) or "- No structural issue was found during analysis."
    return f"""# {stage['title']}\n\n## Purpose\n\n{stage['purpose']}\n\n## Before you begin\n\n1. Open ComfyUI.\n2. Confirm the Pi Agent custom node is loaded.\n3. Run the tutorial preflight node.\n4. Keep the tutorial directory structure unchanged.\n\n## Required node classes\n\n{required_nodes}\n\n## Required models or model-like files\n\n{models}\n\n## Required inputs\n\n{inputs}\n\n## Complete procedure\n\n1. Load `workflow_tutorial.json` in ComfyUI.\n2. Read the numbered canvas groups and Pi Tutorial Note nodes.\n3. Provide every required input file.\n4. Confirm model loaders point to installed, architecture-compatible models.\n5. Review prompts and change only the creative details you understand.\n6. Queue the workflow using ComfyUI's normal Queue button.\n7. Check the output nodes and save the successful result in this stage's output folder.\n8. Run **Pi Tutorial Stage Validate** or the tutorial preflight again.\n9. Mark the stage complete only after its expected files exist.\n\n## Analysis warnings\n\n{issue_text}\n\n## Common problems\n\n- **Red or missing nodes:** install or enable the correct custom-node package, then restart ComfyUI.\n- **Model not found:** choose an installed compatible model. Do not rename an unrelated model to make the error disappear.\n- **GGUF workflow fails:** confirm the GGUF loader, text encoder, VAE, projector, and LoRA path are compatible together.\n- **Out of memory:** lower resolution or batch size, use a validated quantized model, or enable an approved offload profile.\n- **Output differs from the example:** confirm the seed, model revision, workflow version, input references, and prompts.\n\n## Next stage\n\n{stage.get('next_stage') or 'This is the final tutorial stage.'}\n"""


def _annotate_ui_workflow(workflow: dict[str, Any], title: str, report: dict[str, Any]) -> dict[str, Any]:
    annotated = copy.deepcopy(workflow)
    nodes = annotated.get("nodes")
    if not isinstance(nodes, list):
        return annotated
    max_id = 0
    for node in nodes:
        try:
            max_id = max(max_id, int(node.get("id", 0)))
        except Exception:
            pass
    notes = [
        ("START HERE", f"Tutorial workflow: {title}\nRead every numbered group before queuing the workflow."),
        ("REQUIREMENTS", f"Detected {report['node_count']} nodes and {report['link_count']} links. Run Pi Tutorial Preflight before execution."),
        ("FINISH", "Check the expected output, save it in the correct project folder, then validate this tutorial stage.")
    ]
    x = min([float(n.get("pos", [0, 0])[0]) for n in nodes if isinstance(n.get("pos"), list)] or [0]) - 440
    y = min([float(n.get("pos", [0, 0])[1]) for n in nodes if isinstance(n.get("pos"), list)] or [0])
    for offset, (heading, text) in enumerate(notes):
        max_id += 1
        nodes.append({
            "id": max_id,
            "type": "PiTutorialNote",
            "pos": [x, y + offset * 220],
            "size": [380, 160],
            "flags": {},
            "order": 0,
            "mode": 0,
            "inputs": [],
            "outputs": [{"name": "text", "type": "STRING", "links": None, "slot_index": 0}],
            "properties": {"Node name for S&R": "PiTutorialNote"},
            "widgets_values": [heading, text]
        })
    annotated.setdefault("extra", {})["pi_tutorial"] = {"title": title, "compiled_at": _utc(), "report": report}
    return annotated


def _controller_workflow(tutorial_dir: str) -> dict[str, Any]:
    return {
        "last_node_id": 6, "last_link_id": 4,
        "nodes": [
            {"id": 1, "type": "PiTutorialLoad", "pos": [20, 40], "size": [360, 110], "flags": {}, "order": 0, "mode": 0,
             "inputs": [], "outputs": [{"name": "tutorial", "type": "TUTORIAL_PROJECT", "links": [1], "slot_index": 0}, {"name": "json", "type": "STRING", "links": None, "slot_index": 1}], "properties": {}, "widgets_values": [tutorial_dir]},
            {"id": 2, "type": "PiTutorialPreflight", "pos": [440, 40], "size": [360, 130], "flags": {}, "order": 1, "mode": 0,
             "inputs": [{"name": "tutorial", "type": "TUTORIAL_PROJECT", "link": 1}], "outputs": [{"name": "report", "type": "STRING", "links": [2], "slot_index": 0}], "properties": {}, "widgets_values": ["standard"]},
            {"id": 3, "type": "PiTutorialStageSelect", "pos": [440, 230], "size": [360, 130], "flags": {}, "order": 2, "mode": 0,
             "inputs": [{"name": "tutorial", "type": "TUTORIAL_PROJECT", "link": 1}], "outputs": [{"name": "stage", "type": "TUTORIAL_STAGE", "links": [3], "slot_index": 0}, {"name": "json", "type": "STRING", "links": None, "slot_index": 1}], "properties": {}, "widgets_values": [1]},
            {"id": 4, "type": "PiTutorialStageValidate", "pos": [860, 230], "size": [360, 130], "flags": {}, "order": 3, "mode": 0,
             "inputs": [{"name": "stage", "type": "TUTORIAL_STAGE", "link": 3}], "outputs": [{"name": "report", "type": "STRING", "links": [4], "slot_index": 0}], "properties": {}, "widgets_values": ["check_files"]},
            {"id": 5, "type": "PiShowText", "pos": [1280, 230], "size": [440, 180], "flags": {}, "order": 4, "mode": 0,
             "inputs": [{"name": "text", "type": "STRING", "link": 4}], "outputs": [{"name": "text", "type": "STRING", "links": None, "slot_index": 0}], "properties": {}, "widgets_values": []},
            {"id": 6, "type": "PiShowText", "pos": [860, 40], "size": [440, 150], "flags": {}, "order": 5, "mode": 0,
             "inputs": [{"name": "text", "type": "STRING", "link": 2}], "outputs": [{"name": "text", "type": "STRING", "links": None, "slot_index": 0}], "properties": {}, "widgets_values": []}
        ],
        "links": [[1, 1, 0, 2, 0, "TUTORIAL_PROJECT"], [2, 2, 0, 6, 0, "STRING"], [3, 1, 0, 3, 0, "TUTORIAL_PROJECT"], [4, 3, 0, 4, 0, "TUTORIAL_STAGE"]],
        "groups": [{"title": "1 — Load the tutorial", "bounding": [0, 0, 400, 190]}, {"title": "2 — Check requirements", "bounding": [420, 0, 400, 190]}, {"title": "3 — Select and validate a stage", "bounding": [420, 190, 830, 230]}],
        "config": {}, "extra": {"pi_tutorial_controller": True}, "version": 0.4
    }


def _overview_workflow(stages: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = []
    groups = []
    for i, stage in enumerate(stages, 1):
        x = 40 + ((i - 1) % 3) * 460
        y = 40 + ((i - 1) // 3) * 240
        nodes.append({"id": i, "type": "PiTutorialNote", "pos": [x, y], "size": [400, 170], "flags": {}, "order": 0, "mode": 0,
                      "inputs": [], "outputs": [{"name": "text", "type": "STRING", "links": None, "slot_index": 0}], "properties": {},
                      "widgets_values": [f"Stage {i}: {stage['title']}", stage['purpose']]})
        groups.append({"title": f"{i:02d} — {stage['title']}", "bounding": [x - 20, y - 20, 440, 210]})
    return {"last_node_id": len(nodes), "last_link_id": 0, "nodes": nodes, "links": [], "groups": groups, "config": {}, "extra": {"pi_project_overview": True}, "version": 0.4}


def compile_tutorial(workflows_value: str | dict | list, title: str = "ComfyUI Project Tutorial", output_directory: str = "", detail_level: str = "complete") -> dict[str, Any]:
    collection = load_workflow_collection(workflows_value)
    base = resolve_output_root(output_directory, "tutorials")
    root = safe_join(base, slugify(title))
    root.mkdir(parents=True, exist_ok=True)
    for directory in ("00_SETUP", "01_OVERVIEW/diagrams", "02_CONTROLLER", "03_STAGES", "04_WORKFLOWS/original", "04_WORKFLOWS/tutorial", "04_WORKFLOWS/validated", "04_WORKFLOWS/repaired", "04_WORKFLOWS/safetensors", "04_WORKFLOWS/gguf", "05_PROJECT_ASSETS/references", "05_PROJECT_ASSETS/prompts", "05_PROJECT_ASSETS/bibles", "05_PROJECT_ASSETS/scripts", "05_PROJECT_ASSETS/screenplays", "05_PROJECT_ASSETS/storyboards", "05_PROJECT_ASSETS/shot_lists", "05_PROJECT_ASSETS/example_media", "06_MANIFESTS", "07_VALIDATION/reports", "07_VALIDATION/test-results", "07_VALIDATION/execution-errors", "07_VALIDATION/checksums", "08_EDITORIAL/kdenlive", "08_EDITORIAL/otio", "09_EXPORTS"):
        safe_join(root, directory).mkdir(parents=True, exist_ok=True)
    stages = []
    workflows_manifest = []
    all_models = set()
    all_nodes = set()
    for index, item in enumerate(collection, 1):
        name = item["name"]
        workflow = item["workflow"]
        report = analyze_workflow(workflow).to_dict()
        all_models.update(report["model_candidates"])
        all_nodes.update(report["node_types"].keys())
        stage_id = f"stage-{index:02d}"
        stage_dir = safe_join(root, "03_STAGES", f"STAGE_{index:02d}")
        stage_dir.mkdir(parents=True, exist_ok=True)
        for child in ("prompts", "inputs", "expected_outputs", "examples"):
            (stage_dir / child).mkdir(exist_ok=True)
        original_path = safe_join(root, "04_WORKFLOWS", "original", f"{slugify(name)}.json")
        tutorial_path = safe_join(root, "04_WORKFLOWS", "tutorial", f"{slugify(name)}_tutorial.json")
        atomic_write_json(original_path, workflow)
        annotated = _annotate_ui_workflow(workflow, name, report) if report["format"] == "ui" else workflow
        atomic_write_json(tutorial_path, annotated)
        atomic_write_json(stage_dir / "workflow_original.json", workflow)
        atomic_write_json(stage_dir / "workflow_tutorial.json", annotated)
        stage = {
            "stage_id": stage_id,
            "index": index,
            "title": name.replace("_", " ").replace("-", " ").title(),
            "purpose": f"Run and understand the {name} ComfyUI workflow as part of the complete tutorial.",
            "prerequisites": [f"Complete stage {index-1}." ] if index > 1 else ["Complete tutorial setup and preflight."],
            "required_workflows": [str(tutorial_path.relative_to(root))],
            "required_models": report["model_candidates"],
            "required_custom_nodes": sorted(report["node_types"].keys()),
            "required_inputs": report["input_files"],
            "instructions": [], "prompts": [], "expected_outputs": [],
            "validation_rules": [{"type": "workflow_valid", "strict": False}],
            "common_errors": [], "repair_actions": [],
            "issues": report["issues"],
            "next_stage": f"stage-{index+1:02d}" if index < len(collection) else None,
            "optional": False,
            "status": "not_started"
        }
        stages.append(stage)
        atomic_write_json(stage_dir / "stage.json", stage)
        md = _stage_markdown(stage)
        atomic_write_text(stage_dir / "README.md", md)
        write_docx(stage_dir / "README.docx", md, stage["title"])
        workflows_manifest.append({"name": name, "source": item.get("source"), "original": str(original_path.relative_to(root)), "tutorial": str(tutorial_path.relative_to(root)), "analysis": report})

    tutorial = {
        "schema_version": "1.0", "tutorial_id": slugify(title), "title": title,
        "tutorial_type": "workflow_collection" if len(stages) > 1 else "single_workflow",
        "interface": "comfyui_native", "detail_level": detail_level, "compiled_at": _utc(),
        "stages": stages, "workflows": workflows_manifest,
        "models": sorted(all_models), "custom_nodes": sorted(all_nodes),
        "assets": [], "progress": {"current_stage": stages[0]["stage_id"] if stages else None, "completed_stages": []},
        "validation": {"status": "not_run"}
    }
    atomic_write_json(root / "tutorial.json", tutorial)
    atomic_write_json(root / "tutorial-lock.json", {"compiled_at": tutorial["compiled_at"], "workflow_count": len(collection), "format": "comfyui-native"})
    controller = _controller_workflow(str(root))
    overview = _overview_workflow(stages)
    atomic_write_json(safe_join(root, "02_CONTROLLER", "Tutorial_Controller.json"), controller)
    atomic_write_json(safe_join(root, "01_OVERVIEW", "Project_Overview.json"), overview)
    quick = f"""# {title}: Quick Start\n\n1. Install this custom node by cloning it into `ComfyUI/custom_nodes`.\n2. Restart ComfyUI.\n3. Load `02_CONTROLLER/Tutorial_Controller.json`.\n4. Run **Pi Tutorial Preflight**.\n5. Fix every blocking requirement.\n6. Select Stage 1 and load its `workflow_tutorial.json`.\n7. Follow its canvas notes and `README.md`.\n8. Continue in stage order.\n\nThis tutorial runs entirely inside ComfyUI. It does not include or require a separate WebUI.\n"""
    setup = f"""# Requirements\n\n- A current ComfyUI installation\n- This Pi Agent custom node\n- The node classes listed in `06_MANIFESTS/custom-nodes.json`\n- Compatible model components listed in `06_MANIFESTS/models.json`\n- Input assets listed by each stage\n\nRun the controller workflow's preflight node instead of guessing what is missing.\n"""
    overview_md = f"# {title}\n\nThis tutorial contains {len(stages)} stage(s) and {len(all_nodes)} detected node type(s). Follow the stages in order unless the dependency notes explicitly say they can run separately.\n"
    troubleshooting = "# Troubleshooting\n\n## Missing node\n\nInstall or enable the package that owns the exact missing node class, then restart ComfyUI.\n\n## Missing model\n\nChoose an architecture-compatible installed model. Do not invent or rename filenames.\n\n## GGUF problems\n\nCheck the loader, text encoder, VAE, projector, LoRA support, and model revision as a complete component set.\n\n## Workflow changed\n\nRun **Pi Tutorial Update** or compile the tutorial again. Originals remain preserved.\n"
    atomic_write_text(root / "README.md", overview_md + "\n" + quick)
    atomic_write_text(root / "QUICK_START.md", quick)
    write_docx(root / "QUICK_START.docx", quick, f"{title} Quick Start")
    complete = overview_md + "\n" + setup + "\n" + "\n".join(_stage_markdown(s) for s in stages)
    atomic_write_text(root / "COMPLETE_TUTORIAL.md", complete)
    write_docx(root / "COMPLETE_TUTORIAL.docx", complete, title)
    atomic_write_text(root / "TROUBLESHOOTING.md", troubleshooting)
    write_docx(root / "TROUBLESHOOTING.docx", troubleshooting, "Troubleshooting")
    atomic_write_text(safe_join(root, "00_SETUP", "REQUIREMENTS.md"), setup)
    atomic_write_text(safe_join(root, "00_SETUP", "INSTALLATION.md"), quick)
    atomic_write_text(safe_join(root, "00_SETUP", "PREFLIGHT.md"), "# Preflight\n\nLoad the Tutorial Controller workflow and run the Pi Tutorial Preflight node. Blocking items must be fixed before the affected stage runs.\n")
    atomic_write_text(safe_join(root, "01_OVERVIEW", "PROJECT_OVERVIEW.md"), overview_md)
    atomic_write_text(safe_join(root, "01_OVERVIEW", "PIPELINE_OVERVIEW.md"), "# Pipeline Overview\n\n" + "\n".join(f"{i}. {s['title']}" for i, s in enumerate(stages, 1)) + "\n")
    atomic_write_json(safe_join(root, "01_OVERVIEW", "workflow-map.json"), {"stages": [{"id": s["stage_id"], "next": s["next_stage"]} for s in stages]})
    atomic_write_json(safe_join(root, "06_MANIFESTS", "models.json"), {"models": sorted(all_models)})
    atomic_write_json(safe_join(root, "06_MANIFESTS", "custom-nodes.json"), {"node_classes": sorted(all_nodes)})
    atomic_write_json(safe_join(root, "06_MANIFESTS", "workflows.json"), {"workflows": workflows_manifest})
    atomic_write_json(safe_join(root, "06_MANIFESTS", "assets.json"), {"assets": []})
    atomic_write_json(safe_join(root, "06_MANIFESTS", "dependencies.json"), {"stages": [{"stage": s["stage_id"], "depends_on": [stages[s["index"]-2]["stage_id"]] if s["index"] > 1 else []} for s in stages]})
    atomic_write_json(safe_join(root, "06_MANIFESTS", "compatibility.json"), {"interface": "comfyui_native", "standalone_webui": False})
    return {"tutorial_directory": str(root), "tutorial": tutorial, "controller_workflow": str(safe_join(root, "02_CONTROLLER", "Tutorial_Controller.json")), "overview_workflow": str(safe_join(root, "01_OVERVIEW", "Project_Overview.json"))}


def load_tutorial(directory: str) -> dict[str, Any]:
    path = Path(directory).expanduser().resolve() / "tutorial.json"
    if not path.is_file():
        raise FileNotFoundError(f"Tutorial manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def tutorial_preflight(tutorial: dict[str, Any], mode: str = "standard") -> dict[str, Any]:
    registry = get_live_node_registry()
    installed_models = inventory_models()
    installed_names = {row["name"] for rows in installed_models.get("categories", {}).values() for row in rows}
    missing_nodes = sorted(n for n in tutorial.get("custom_nodes", []) if registry and n not in registry and n not in {"Reroute", "Note"})
    missing_models = sorted(m for m in tutorial.get("models", []) if m not in installed_names)
    status = "ready"
    if missing_nodes or missing_models:
        status = "blocked"
    return {
        "status": status, "mode": mode, "missing_node_classes": missing_nodes,
        "missing_model_files": missing_models, "installed_model_count": installed_models.get("total", 0),
        "message": "Ready." if status == "ready" else "Fix blocking items before running affected stages."
    }


def select_stage(tutorial: dict[str, Any], index: int) -> dict[str, Any]:
    stages = tutorial.get("stages", [])
    if not stages:
        raise ValueError("Tutorial has no stages.")
    normalized = min(max(int(index), 1), len(stages))
    return stages[normalized - 1]


def validate_stage(stage: dict[str, Any], mode: str = "check_files") -> dict[str, Any]:
    issues = stage.get("issues", [])
    errors = [i for i in issues if i.get("severity") == "error"]
    return {"valid": not errors, "mode": mode, "stage_id": stage.get("stage_id"), "errors": errors, "warnings": [i for i in issues if i.get("severity") != "error"]}
