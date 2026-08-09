from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compat import get_comfy_search_paths, get_model_filenames
from .io_utils import load_json

MODEL_CATEGORIES = [
    "checkpoints", "diffusion_models", "unet", "text_encoders", "clip",
    "clip_vision", "vae", "loras", "controlnet", "audio_encoders",
    "model_patches", "upscale_models"
]


def inventory_models(limit_per_category: int = 500) -> dict[str, Any]:
    categories: dict[str, list[dict[str, str]]] = {}
    search_paths: dict[str, list[str]] = {}
    total = 0
    for category in MODEL_CATEGORIES:
        paths = [str(path) for path in get_comfy_search_paths(category, existing_only=False)]
        if paths:
            search_paths[category] = paths
        files = get_model_filenames(category)[: max(1, limit_per_category)]
        rows = []
        for filename in files:
            suffix = Path(filename).suffix.lower().lstrip(".") or "directory"
            rows.append({"name": filename, "format": suffix})
        if rows:
            categories[category] = rows
            total += len(rows)
    return {
        "total": total,
        "categories": categories,
        "search_paths": search_paths,
        "search_path_source": "live_comfyui_folder_paths",
    }


def _flatten_inventory(inventory: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for category, rows in inventory.get("categories", {}).items():
        for row in rows:
            result.append({"category": category, **row})
    return result


def resolve_model(model_family: str, preferred_format: str, inventory_value: str | dict | None = None) -> dict[str, Any]:
    inventory = load_json(inventory_value, default=None) if inventory_value else None
    if not isinstance(inventory, dict):
        inventory = inventory_models()
    aliases = [token for token in model_family.lower().replace("_", "-").split("-") if token]
    candidates = []
    for row in _flatten_inventory(inventory):
        lowered = row["name"].lower()
        score = sum(1 for alias in aliases if alias in lowered)
        if score:
            format_bonus = 2 if preferred_format != "auto" and row["format"] == preferred_format else 0
            candidates.append({**row, "score": score + format_bonus})
    candidates.sort(key=lambda row: (-row["score"], row["name"]))
    selected = candidates[0] if candidates else None
    return {
        "model_family": model_family,
        "preferred_format": preferred_format,
        "selected": selected,
        "candidates": candidates[:25],
        "warning": None if selected else "No matching installed model was found. The plugin did not invent a filename."
    }


def load_profiles() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "data" / "model_profiles.json"
    return json.loads(path.read_text(encoding="utf-8"))
