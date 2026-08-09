from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .discovery import installation_search_context

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "pi" / "bundled-skills"

# This is intentionally short. It is stable operating policy, not domain knowledge.
# Domain procedures are selected lazily below so small models receive useful structure
# without paying for the entire skill library on every turn.
CORE_AGENT_CONTRACT = """ComfyUI-Pi operating contract:
1. Stay on the user's current task. Do not broaden the job or restart completed work.
2. Act when the user asked for work. Do not replace execution with a plan unless execution is impossible or the user asked only for a plan.
3. Inspect before guessing. For workflows, nodes, models, files, errors, and paths, use available live/file evidence. Before searching the ComfyUI installation, use the live ComfyUI search-path/installed-asset tools or the live runtime paths supplied in the current-job context; never assume only default models, workflows, or custom_nodes directories because the running instance may load extra_model_paths.yaml or --extra-model-paths-config roots. Never invent node classes, model filenames, paths, or success claims.
4. For multi-step work, follow dependency order and keep a small internal checklist: target -> inspect -> change/create -> validate -> finish.
5. Make the smallest safe change. Preserve originals and user-approved/locked/manual work. Never silently overwrite important artifacts. Preserve exact filenames, node IDs, paths, and user wording when they are identifiers.
6. Use tools conservatively: prefer exact reads/edits over broad shell operations; never use destructive shell commands when a targeted operation is sufficient.
7. After a change, validate the thing that changed. For a failure, use the exact error, isolate one cause, repair it, and validate again.
8. Do not repeatedly ask questions when the answer can be discovered from the workflow, project, files, live ComfyUI schemas, or safe defaults. If truly blocked, state exactly what is missing.
9. Keep large data out of context. Read large referenced files only when the current task needs their exact contents.
10. Treat dynamically loaded skills/integrations as procedures. Follow only those relevant to the current task and validate against the installed environment.
11. Workflow generation is a fail-closed build gate: use only node classes registered in the current ComfyUI instance; use the current live socket schemas for every connection; generate Nodes 2.0 UI workflows with extra.workflowRendererVersion=Vue-corrected; keep at least 6 pixels between every pair of nodes; require a real OUTPUT_NODE path; and run the ComfyUI-Pi workflow finalizer/native prompt preflight before calling a workflow complete or runnable.
12. Finish with evidence: what was completed, exact files/workflows changed or created, validation performed, and any remaining blocker. Never claim completion without evidence."""


@dataclass(frozen=True)
class SkillMatch:
    name: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Deterministic routes are preferable to asking a small LLM to decide which manual it needs.
# Keep generic routing here; node-pack integrations have their own lazy router.
_RULES: dict[str, dict[str, Any]] = {
    "workflow-intelligence": {
        "phrases": ["workflow", "node graph", "comfy graph", "repair workflow", "edit workflow", "create workflow", "node"],
        "weight": 5,
    },
    "comfyui-tutorial-compile": {
        "phrases": ["tutorial", "walkthrough", "how to complete", "document workflow", "teach this workflow"],
        "weight": 8,
    },
    "comfyui-tutorial-update": {
        "phrases": ["update tutorial", "repair tutorial", "tutorial changed", "revise tutorial"],
        "weight": 9,
    },
    "complete-production": {
        "phrases": ["complete production", "complete project", "entire project", "movie", "film project", "music video", "production package"],
        "weight": 7,
    },
    "incremental-production-compiler": {
        "phrases": ["compile project", "resume project", "continue project", "missing assets", "stale assets", "recompile", "compile scene", "compile shot"],
        "weight": 8,
    },
    "narrative-project": {
        "phrases": ["story", "book", "novel", "novella", "chapter", "manuscript", "outline", "beat sheet"],
        "weight": 5,
    },
    "fountain-screenplay": {
        "phrases": ["fountain", "screenplay", "screen play", "teleplay", "script"],
        "weight": 6,
    },
    "story-to-screenplay": {
        "phrases": ["story to screenplay", "book to screenplay", "adapt to screenplay", "adaptation"],
        "weight": 10,
    },
    "screenplay-breakdown": {
        "phrases": ["screenplay breakdown", "break down screenplay", "scene breakdown", "production breakdown", "scene list"],
        "weight": 9,
    },
    "shot-planning": {
        "phrases": ["shot list", "shot plan", "camera coverage", "coverage plan", "shots"],
        "weight": 7,
    },
    "storyboard": {
        "phrases": ["storyboard", "story board", "shot board", "animatic"],
        "weight": 8,
    },
    "moodboard": {
        "phrases": ["mood board", "moodboard", "look development", "style board", "color script"],
        "weight": 8,
    },
    "reference-asset-system": {
        "phrases": ["reference asset", "reference sheet", "production bible", "visual bible", "reference collection"],
        "weight": 7,
    },
    "character-reference": {
        "phrases": ["character reference", "character sheet", "turnaround", "expression sheet", "pose sheet", "character consistency"],
        "weight": 9,
    },
    "voice-reference": {
        "phrases": ["voice reference", "speaker profile", "voice clone", "voice cloning", "pronunciation reference"],
        "weight": 9,
    },
    "music-audio-reference": {
        "phrases": ["music reference", "audio reference", "sound reference", "ambience reference", "mix reference"],
        "weight": 8,
    },
    "image-generation-router": {
        "phrases": ["generate image", "image generation", "text to image", "image workflow", "create image"],
        "weight": 5,
    },
    "qwen-image": {"phrases": ["qwen image"], "weight": 10},
    "qwen-image-edit": {"phrases": ["qwen image edit", "qwen edit"], "weight": 11},
    "krea-2-image": {"phrases": ["krea 2", "krea2", "krea raw", "krea turbo"], "weight": 9},
    "krea-2-edit": {"phrases": ["krea 2 edit", "krea2 edit", "identity edit"], "weight": 11},
    "flux-2-klein-image": {"phrases": ["flux.2", "flux 2", "klein"], "weight": 10},
    "z-image": {"phrases": ["z-image", "z image"], "weight": 10},
    "audio-generation-router": {
        "phrases": ["generate audio", "audio workflow", "sound effect", "sound effects", "generate music", "speech workflow", "dialogue audio"],
        "weight": 5,
    },
    "ace-step-1-5": {"phrases": ["ace-step", "ace step", "acestep"], "weight": 10},
    "qwen3-tts": {"phrases": ["qwen3-tts", "qwen3 tts", "qwen tts"], "weight": 10},
    "stable-audio-3": {"phrases": ["stable audio 3", "stableaudio3"], "weight": 10},
    "gguf-model-resolution": {
        "phrases": ["gguf", "quantized model", "quantized checkpoint", "model substitution"],
        "weight": 9,
    },
    "kdenlive-handoff": {
        "phrases": ["kdenlive", "nle", "editorial package", "editing package", "otio", "opentimelineio"],
        "weight": 9,
    },
    "document-export": {
        "phrases": [
            "docx", "markdown export", "save markdown", "export document", "export text",
            "diagram", "flowchart", "ascii flowchart", "markdown diagram",
            "diagram image", "node image", "comfyui node image",
            "screenshot", "workflow screenshot", "node screenshot", "tutorial screenshot",
        ],
        "weight": 8,
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _phrase_matches(text: str, phrase: str) -> bool:
    phrase = _normalize(phrase)
    if not phrase:
        return False
    if " " in phrase or any(ch in phrase for ch in ".-"):
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def select_skills(message: str, workflow: Any = None, max_skills: int = 3) -> list[SkillMatch]:
    text = _normalize(message)
    matches: list[SkillMatch] = []
    workflow_present = workflow not in (None, "", {})

    for name, rule in _RULES.items():
        hits = [p for p in rule.get("phrases", []) if _phrase_matches(text, str(p))]
        score = int(rule.get("weight", 1)) * len(hits)
        reason = ", ".join(hits[:3])
        if name == "workflow-intelligence" and workflow_present:
            score += 7
            reason = (reason + ", attached workflow").strip(", ")
        if score > 0:
            matches.append(SkillMatch(name=name, score=score, reason=reason or "task match"))

    # A supplied workflow should always get workflow procedure, even for terse follow-ups like "fix it".
    if workflow_present and not any(item.name == "workflow-intelligence" for item in matches):
        matches.append(SkillMatch("workflow-intelligence", 7, "attached workflow"))

    # If a specific skill is selected, remove its generic router when space is tight unless the
    # generic procedure adds materially different behavior.
    matches.sort(key=lambda item: (-item.score, item.name))
    selected: list[SkillMatch] = []
    for item in matches:
        if item.name in {"image-generation-router", "audio-generation-router"}:
            family = "image" if item.name.startswith("image") else "audio"
            specific = any(
                (family == "image" and m.name in {"qwen-image", "qwen-image-edit", "krea-2-image", "krea-2-edit", "flux-2-klein-image", "z-image"})
                or (family == "audio" and m.name in {"ace-step-1-5", "qwen3-tts", "stable-audio-3"})
                for m in matches
            )
            if specific:
                continue
        selected.append(item)
        if len(selected) >= max(1, min(4, int(max_skills))):
            break
    return selected


def _load_skill(name: str, max_chars: int = 2500) -> str:
    path = SKILLS_ROOT / name / "SKILL.md"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0] + "\n[skill truncated to preserve context]"


def build_skill_context(matches: list[SkillMatch], max_total_chars: int = 6500) -> str:
    sections: list[str] = []
    total = 0
    for item in matches:
        text = _load_skill(item.name)
        if not text:
            continue
        block = f"### Procedure: {item.name}\n{text}"
        if total + len(block) > max_total_chars:
            remaining = max_total_chars - total
            if remaining > 500:
                sections.append(block[:remaining].rsplit("\n", 1)[0])
            break
        sections.append(block)
        total += len(block)
    return "\n\n".join(sections)


def task_kind(message: str, selected: list[SkillMatch]) -> str:
    names = {item.name for item in selected}
    if "workflow-intelligence" in names:
        return "workflow"
    if names & {"complete-production", "incremental-production-compiler"}:
        return "production"
    if names & {"fountain-screenplay", "story-to-screenplay", "screenplay-breakdown", "shot-planning", "storyboard"}:
        return "screenplay-production"
    if "narrative-project" in names:
        return "writing"
    if "document-export" in names:
        return "writing"
    if names & {"image-generation-router", "qwen-image", "qwen-image-edit", "krea-2-image", "krea-2-edit", "flux-2-klein-image", "z-image"}:
        return "image"
    if names & {"audio-generation-router", "ace-step-1-5", "qwen3-tts", "stable-audio-3"}:
        return "audio"
    if "kdenlive-handoff" in names:
        return "editorial"
    return "general"


def completion_rule(kind: str) -> str:
    rules = {
        "workflow": "Use only current-instance live nodes and exact live socket schemas; create Nodes 2.0/Vue-corrected UI graphs; organize every node with at least 6px clearance; require a real output path; validate the resulting workflow with the strict workflow finalizer and ComfyUI native prompt preflight; do not call the workflow complete/runnable until those checks pass.",
        "production": "Advance the requested project scope until every required stage in that scope is completed or a concrete blocker is proven; do not call partial work complete.",
        "screenplay-production": "Preserve source/story continuity, create only the requested screenplay/scene/shot artifacts, validate structure, and keep traceability between source and production artifacts.",
        "writing": "Produce or edit the requested narrative artifact, preserve established facts/constraints, and report the exact saved/exported artifact when file output was requested.",
        "image": "Use an installed compatible model/workflow profile, preserve requested references/constraints, validate required components, and do not invent model filenames.",
        "audio": "Use an installed compatible audio/voice/music profile, validate model/workflow requirements and durations/formats, and preserve source references.",
        "editorial": "Create or validate the requested editorial/NLE package with resolvable media paths and clearly report any fallback or missing native feature.",
        "general": "Answer or perform exactly the current request, verify claims that depend on files/tools, and stop when the requested outcome is reached.",
    }
    return rules.get(kind, rules["general"])


def build_task_envelope(message: str, matches: list[SkillMatch], workflow_present: bool = False) -> str:
    kind = task_kind(message, matches)
    skill_names = ", ".join(item.name for item in matches) if matches else "none"
    workflow_line = "An active/supplied workflow is available; inspect its exact file only if the task needs graph-level details." if workflow_present else "No workflow graph was supplied with this turn."
    envelope = (
        "CURRENT JOB (do not drift):\n"
        f"- User instruction: {str(message or '').strip()}\n"
        f"- Task class: {kind}\n"
        f"- Selected procedures: {skill_names}\n"
        f"- Completion rule: {completion_rule(kind)}\n"
        f"- Context rule: {workflow_line}"
    )
    installation = installation_search_context(message)
    return f"{envelope}\n\n{installation}" if installation else envelope


def build_request_guidance(message: str, workflow: Any = None, max_skills: int = 3) -> dict[str, Any]:
    matches = select_skills(message, workflow=workflow, max_skills=max_skills)
    return {
        "core_contract": CORE_AGENT_CONTRACT,
        "task_envelope": build_task_envelope(message, matches, workflow_present=workflow not in (None, "", {})),
        "loaded_skills": [item.to_dict() for item in matches],
        "skill_context": build_skill_context(matches),
    }


def guidance_signature(guidance: dict[str, Any]) -> str:
    return json.dumps(
        [item.get("name") for item in guidance.get("loaded_skills", []) if isinstance(item, dict)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
