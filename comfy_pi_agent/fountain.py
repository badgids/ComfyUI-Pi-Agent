from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

SCENE_RE = re.compile(r"^(INT\.?|EXT\.?|INT\./EXT\.?|EXT\./INT\.?|I/E\.?)[ -].+", re.IGNORECASE)
CHAR_RE = re.compile(r"^[A-Z0-9 ._'\-()]+$")


@dataclass
class FountainElement:
    type: str
    text: str
    line: int
    scene_number: str | None = None


def build_fountain(title: str, author: str, story_text: str, default_location: str = "UNSPECIFIED LOCATION") -> str:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", story_text.strip()) if p.strip()]
    lines = [f"Title: {title}", "Credit: Written by", f"Author: {author}", "", f"INT. {default_location.upper()} - DAY", ""]
    for paragraph in paragraphs:
        if SCENE_RE.match(paragraph.splitlines()[0].strip()):
            lines.extend([paragraph, ""])
        else:
            lines.extend([paragraph, ""])
    return "\n".join(lines).rstrip() + "\n"


def parse_fountain(text: str) -> dict[str, Any]:
    elements: list[FountainElement] = []
    title_page: dict[str, str] = {}
    in_title = True
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        line_no = i + 1
        if in_title and stripped and ":" in stripped and not SCENE_RE.match(stripped):
            key, value = stripped.split(":", 1)
            title_page[key.strip().lower().replace(" ", "_")] = value.strip()
            elements.append(FountainElement("title_page", stripped, line_no))
            i += 1
            continue
        if not stripped:
            if in_title:
                in_title = False
            i += 1
            continue
        in_title = False
        scene_number = None
        scene_text = stripped
        if SCENE_RE.match(stripped.lstrip(".")):
            match = re.search(r"\s+#([^#]+)#\s*$", stripped)
            if match:
                scene_number = match.group(1).strip()
                scene_text = stripped[: match.start()].rstrip()
            elements.append(FountainElement("scene_heading", scene_text.lstrip("."), line_no, scene_number))
        elif stripped.startswith(">") and stripped.endswith("<"):
            elements.append(FountainElement("centered", stripped[1:-1].strip(), line_no))
        elif stripped.startswith(">"):
            elements.append(FountainElement("transition", stripped.lstrip("> "), line_no))
        elif stripped.startswith("#"):
            elements.append(FountainElement("section", stripped.lstrip("# "), line_no))
        elif stripped.startswith("="):
            elements.append(FountainElement("synopsis", stripped.lstrip("= "), line_no))
        elif stripped.startswith("[[") and stripped.endswith("]]" ):
            elements.append(FountainElement("note", stripped[2:-2].strip(), line_no))
        elif stripped == "===" :
            elements.append(FountainElement("page_break", "", line_no))
        elif CHAR_RE.match(stripped.rstrip("^")) and stripped == stripped.upper() and len(stripped) <= 45:
            elements.append(FountainElement("character", stripped, line_no))
        elif stripped.startswith("(") and stripped.endswith(")"):
            elements.append(FountainElement("parenthetical", stripped, line_no))
        elif elements and elements[-1].type in {"character", "parenthetical", "dialogue"}:
            elements.append(FountainElement("dialogue", stripped, line_no))
        else:
            elements.append(FountainElement("action", stripped, line_no))
        i += 1

    scenes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for element in elements:
        if element.type == "scene_heading":
            if current:
                scenes.append(current)
            current = {
                "scene_id": f"scene-{len(scenes)+1:03d}",
                "scene_number": element.scene_number or str(len(scenes)+1),
                "heading": element.text,
                "characters": [],
                "action": [],
                "dialogue": [],
                "elements": []
            }
        if current:
            current["elements"].append(asdict(element))
            if element.type == "character":
                name = element.text.rstrip("^").strip()
                if name not in current["characters"]:
                    current["characters"].append(name)
            elif element.type == "action":
                current["action"].append(element.text)
            elif element.type == "dialogue":
                current["dialogue"].append(element.text)
    if current:
        scenes.append(current)
    return {"title_page": title_page, "elements": [asdict(e) for e in elements], "scenes": scenes}


def validate_fountain(text: str) -> dict[str, Any]:
    parsed = parse_fountain(text)
    issues: list[dict[str, Any]] = []
    if not parsed["scenes"]:
        issues.append({"severity": "warning", "code": "no_scenes", "message": "No Fountain scene headings were found."})
    seen = set()
    for scene in parsed["scenes"]:
        number = scene["scene_number"]
        if number in seen:
            issues.append({"severity": "error", "code": "duplicate_scene_number", "message": f"Duplicate scene number: {number}"})
        seen.add(number)
        if not scene["action"] and not scene["dialogue"]:
            issues.append({"severity": "warning", "code": "empty_scene", "message": f"Scene {number} has no action or dialogue."})
    return {"valid": not any(i["severity"] == "error" for i in issues), "issues": issues, "parsed": parsed}


def screenplay_breakdown(text: str) -> dict[str, Any]:
    parsed = parse_fountain(text)
    scenes = []
    for scene in parsed["scenes"]:
        heading = scene["heading"]
        location = heading
        time_of_day = "UNKNOWN"
        if " - " in heading:
            location, time_of_day = heading.rsplit(" - ", 1)
        scenes.append({
            "scene_id": scene["scene_id"],
            "scene_number": scene["scene_number"],
            "heading": heading,
            "location": location,
            "time_of_day": time_of_day,
            "characters": scene["characters"],
            "summary": " ".join(scene["action"][:2]),
            "dialogue_line_count": len(scene["dialogue"]),
            "visual_requirements": [],
            "audio_requirements": [],
            "continuity_requirements": [],
            "shot_list_status": "missing"
        })
    return {"title": parsed["title_page"].get("title", "Untitled"), "scenes": scenes}


def create_shot_list(breakdown: dict[str, Any], coverage: str = "standard") -> dict[str, Any]:
    shots = []
    for scene in breakdown.get("scenes", []):
        scene_id = scene["scene_id"]
        scene_number = scene["scene_number"]
        templates = [
            ("01", "wide establishing shot", "static", "Establish the location and every important character."),
            ("02", "medium shot", "subtle push-in", "Cover the main scene action."),
            ("03", "close-up", "static", "Capture the most important reaction or story detail.")
        ]
        if coverage == "minimal":
            templates = templates[:2]
        elif coverage == "detailed":
            templates.extend([
                ("04", "insert shot", "static", "Show an important prop or action detail."),
                ("05", "reverse angle", "static", "Provide editorial coverage and preserve screen direction.")
            ])
        for shot_no, size, movement, purpose in templates:
            shots.append({
                "shot_id": f"{scene_number}-{shot_no}",
                "scene_id": scene_id,
                "scene_number": scene_number,
                "shot_number": shot_no,
                "shot_size": size,
                "camera_movement": movement,
                "purpose": purpose,
                "subject": ", ".join(scene.get("characters", [])) or scene.get("location", "scene"),
                "action": scene.get("summary", ""),
                "references": [],
                "status": "planned"
            })
    return {"coverage": coverage, "shots": shots}
