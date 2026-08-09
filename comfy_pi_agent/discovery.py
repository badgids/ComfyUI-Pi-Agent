"""Live ComfyUI installation discovery backed by the running folder_paths registry."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from .compat import (
    get_comfy_search_path_registry,
    get_comfy_search_paths,
    get_comfy_workflow_roots,
    get_model_filenames,
)

MODEL_CATEGORIES = (
    "checkpoints", "diffusion_models", "unet", "text_encoders", "clip",
    "clip_vision", "vae", "loras", "controlnet", "audio_encoders",
    "model_patches", "upscale_models",
)
WORKFLOW_DIR_NAMES = (
    "example_workflows",
    "workflows",
    "workflow",
    os.path.join("examples", "workflows"),
)
SKIP_SCAN_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}


def _dedupe_paths(values: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        try:
            path = Path(value).expanduser().resolve()
        except Exception:
            path = Path(value).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _path_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _dedupe_paths(paths):
        rows.append({
            "path": str(path),
            "exists": path.exists(),
            "is_directory": path.is_dir(),
        })
    return rows


def _custom_node_workflow_roots() -> list[Path]:
    roots: list[Path] = []
    for custom_root in get_comfy_search_paths("custom_nodes", existing_only=True):
        candidates: list[Path] = [custom_root]
        try:
            candidates.extend(child for child in custom_root.iterdir() if child.is_dir())
        except OSError:
            pass
        for pack in candidates:
            for relative in WORKFLOW_DIR_NAMES:
                candidate = pack / relative
                if candidate.is_dir():
                    roots.append(candidate)
    return _dedupe_paths(roots)


def search_path_inventory() -> dict[str, Any]:
    """Describe the live ComfyUI search-path registry used by discovery."""
    registry = get_comfy_search_path_registry(existing_only=False)
    workflow_roots = _dedupe_paths([
        *get_comfy_workflow_roots(existing_only=False),
        *_custom_node_workflow_roots(),
    ])
    return {
        "source": "live_comfyui_folder_paths",
        "categories": {name: _path_rows(paths) for name, paths in registry.items()},
        "custom_node_roots": _path_rows(get_comfy_search_paths("custom_nodes", existing_only=False)),
        "workflow_roots": _path_rows(workflow_roots),
        "notes": [
            "The live registry already includes ComfyUI defaults and startup path overrides.",
            "It also includes extra_model_paths.yaml and --extra-model-paths-config entries loaded by this ComfyUI process.",
        ],
    }


def installation_search_context(message: str, max_chars: int = 2500) -> str:
    """Return a bounded live-path digest only for installation/discovery requests."""
    text = str(message or "").lower()
    subjects = (
        "model", "checkpoint", "lora", "vae", "encoder", "workflow",
        "custom node", "custom_nodes", "node pack", "installed", "installation",
        "comfyui path", "search path",
    )
    actions = (
        "find", "search", "locate", "look for", "where", "which", "what",
        "list", "show", "installed", "available", "missing", "detect", "discover",
    )
    if not any(term in text for term in subjects) or not any(term in text for term in actions):
        return ""

    registry = get_comfy_search_path_registry(existing_only=False)
    if not registry:
        return ""

    lines = [
        "LIVE COMFYUI SEARCH PATHS (runtime-authoritative; includes loaded extra path configs):",
    ]
    for category, roots in registry.items():
        if not roots:
            continue
        joined = " | ".join(str(path) for path in roots)
        lines.append(f"- {category}: {joined}")
        if len("\n".join(lines)) >= max_chars - 300:
            lines.append("- [additional live categories omitted from prompt; use comfyui_search_paths/comfyui_find_installed when available]")
            break

    workflow_roots = get_comfy_workflow_roots(existing_only=False)
    if workflow_roots:
        lines.append("- workflow roots: " + " | ".join(str(path) for path in workflow_roots))
    lines.append("Search these live registered roots instead of assuming only default ComfyUI directories.")
    return "\n".join(lines)[:max(500, int(max_chars))]


def _registered_model_categories() -> list[str]:
    registry = get_comfy_search_path_registry(existing_only=False)
    excluded = {"custom_nodes", "workflows", "workflow"}
    ordered = [category for category in MODEL_CATEGORIES if category in registry]
    ordered.extend(
        category for category in registry
        if category not in excluded and category not in ordered
    )
    return ordered or list(MODEL_CATEGORIES)


def _matches(query: str, *values: object) -> bool:
    needle = str(query or "").strip().lower()
    if not needle:
        return True
    return needle in " ".join(str(value or "") for value in values).lower()


def _existing_model_paths(category: str, filename: str) -> list[str]:
    result: list[str] = []
    for root in get_comfy_search_paths(category, existing_only=False):
        candidate = root / filename
        try:
            if candidate.exists():
                result.append(str(candidate.resolve()))
        except OSError:
            continue
    return result


def _iter_workflow_files(roots: Iterable[Path], scan_limit: int = 10000):
    scanned = 0
    seen: set[str] = set()
    for root in _dedupe_paths(roots):
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in SKIP_SCAN_DIRS and not name.startswith(".")]
            for filename in filenames:
                scanned += 1
                if scanned > scan_limit:
                    return
                if not filename.lower().endswith(".json"):
                    continue
                path = Path(dirpath) / filename
                try:
                    key = str(path.resolve())
                except Exception:
                    key = str(path)
                if key in seen:
                    continue
                seen.add(key)
                yield path


def _append_match(matches: list[dict[str, Any]], seen: set[tuple[str, str, str]], row: dict[str, Any], limit: int) -> bool:
    key = (
        str(row.get("kind") or ""),
        str(row.get("category") or ""),
        str(row.get("path") or row.get("name") or ""),
    )
    if key in seen:
        return False
    seen.add(key)
    matches.append(row)
    return len(matches) >= limit


def find_installed_assets(
    query: str = "",
    kinds: list[str] | tuple[str, ...] | None = None,
    categories: list[str] | tuple[str, ...] | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Search installed models, workflows, custom-node packs, or registered categories.

    Results are derived from the running ComfyUI search-path registry. No default-only
    filesystem assumption is used.
    """
    requested_categories = [str(item).strip() for item in (categories or ()) if str(item).strip()]
    if kinds is None:
        requested_kinds = ["registered"] if requested_categories else ["models", "workflows", "custom_nodes"]
    else:
        requested_kinds = [str(item).strip().lower() for item in kinds if str(item).strip()]
    max_results = max(1, min(500, int(limit or 200)))
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    truncated = False

    if "models" in requested_kinds:
        model_categories = requested_categories or _registered_model_categories()
        for category in model_categories:
            for filename in get_model_filenames(category):
                paths = _existing_model_paths(category, filename)
                if not _matches(query, filename, category, *paths):
                    continue
                row = {
                    "kind": "model",
                    "category": category,
                    "name": filename,
                    "paths": paths,
                }
                if _append_match(matches, seen, row, max_results):
                    truncated = True
                    break
            if truncated:
                break

    if not truncated and "custom_nodes" in requested_kinds:
        for root in get_comfy_search_paths("custom_nodes", existing_only=True):
            candidates: list[Path] = []
            try:
                candidates = sorted(root.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                candidates = []
            for candidate in candidates:
                if candidate.name.startswith(".") or candidate.name == "__pycache__":
                    continue
                if not (candidate.is_dir() or candidate.suffix.lower() == ".py"):
                    continue
                if not _matches(query, candidate.name, candidate, root):
                    continue
                row = {
                    "kind": "custom_node",
                    "category": "custom_nodes",
                    "name": candidate.stem if candidate.is_file() else candidate.name,
                    "path": str(candidate),
                    "root": str(root),
                }
                if _append_match(matches, seen, row, max_results):
                    truncated = True
                    break
            if truncated:
                break

    if not truncated and "workflows" in requested_kinds:
        workflow_roots = _dedupe_paths([
            *get_comfy_workflow_roots(existing_only=True),
            *_custom_node_workflow_roots(),
        ])
        for path in _iter_workflow_files(workflow_roots):
            if not _matches(query, path.name, path):
                continue
            row = {
                "kind": "workflow",
                "category": "workflows",
                "name": path.name,
                "path": str(path),
            }
            if _append_match(matches, seen, row, max_results):
                truncated = True
                break

    if not truncated and requested_categories:
        for category in requested_categories:
            if "models" in requested_kinds and category in model_categories:
                continue
            for filename in get_model_filenames(category):
                paths = _existing_model_paths(category, filename)
                if not _matches(query, filename, category, *paths):
                    continue
                row = {
                    "kind": "registered_file",
                    "category": category,
                    "name": filename,
                    "paths": paths,
                }
                if _append_match(matches, seen, row, max_results):
                    truncated = True
                    break
            if truncated:
                break

    return {
        "query": str(query or ""),
        "kinds": requested_kinds,
        "categories": requested_categories,
        "count": len(matches),
        "limit": max_results,
        "truncated": truncated,
        "matches": matches,
    }
