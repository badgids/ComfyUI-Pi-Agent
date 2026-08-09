"""Small compatibility helpers that keep imports safe outside ComfyUI."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def get_folder_paths_module():
    try:
        import folder_paths  # type: ignore
        return folder_paths
    except Exception:
        return None


def _dedupe_paths(values: Iterable[Any], existing_only: bool = False) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue
        try:
            path = Path(str(value)).expanduser().resolve()
        except Exception:
            path = Path(str(value)).expanduser()
        if existing_only and not path.exists():
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def get_comfy_search_paths(category: str, existing_only: bool = False) -> list[Path]:
    """Return the running ComfyUI instance's registered roots for one category.

    ComfyUI loads its defaults, --base-directory/--models-directory overrides,
    extra_model_paths.yaml, and every --extra-model-paths-config file into the live
    folder_paths registry before custom nodes are imported. Reading that registry is
    therefore more accurate than reparsing one assumed YAML file ourselves.
    """
    name = str(category or "").strip()
    if not name:
        return []
    fp = get_folder_paths_module()
    if fp is None:
        return []

    values: list[Any] = []
    get_paths = getattr(fp, "get_folder_paths", None)
    if callable(get_paths):
        try:
            values = list(get_paths(name) or [])
        except Exception:
            values = []

    # Compatibility fallback for older/current variants where a category is present in
    # the public registry but get_folder_paths() is unavailable or rejects the key.
    if not values:
        registry = getattr(fp, "folder_names_and_paths", None)
        if isinstance(registry, dict):
            entry = registry.get(name)
            if isinstance(entry, (list, tuple)) and entry:
                raw_paths = entry[0]
                if isinstance(raw_paths, (list, tuple, set)):
                    values = list(raw_paths)

    return _dedupe_paths(values, existing_only=existing_only)


def get_comfy_search_path_registry(existing_only: bool = False) -> dict[str, list[Path]]:
    """Snapshot every category currently registered by ComfyUI folder_paths."""
    fp = get_folder_paths_module()
    if fp is None:
        return {}
    registry = getattr(fp, "folder_names_and_paths", None)
    if not isinstance(registry, dict):
        return {}
    result: dict[str, list[Path]] = {}
    for category in sorted(str(key) for key in registry.keys()):
        paths = get_comfy_search_paths(category, existing_only=existing_only)
        if paths:
            result[category] = paths
    return result


def get_comfy_workflow_roots(existing_only: bool = True) -> list[Path]:
    """Return live configured workflow roots plus ComfyUI's standard user workflow roots."""
    roots: list[Path] = []
    # extra_model_paths.yaml accepts arbitrary keys and registers them through
    # add_model_folder_path(), so honor both common spellings when users configure them.
    roots.extend(get_comfy_search_paths("workflows", existing_only=False))
    roots.extend(get_comfy_search_paths("workflow", existing_only=False))

    user_root = get_comfy_user_directory()
    roots.extend([
        user_root / "default" / "workflows",
        user_root / "workflows",
    ])
    return _dedupe_paths(roots, existing_only=existing_only)


def get_comfy_user_directory() -> Path:
    fp = get_folder_paths_module()
    if fp is not None:
        for name in ("get_user_directory", "get_output_directory"):
            fn = getattr(fp, name, None)
            if callable(fn):
                try:
                    path = Path(fn()).expanduser().resolve()
                    return path
                except Exception:
                    pass
    return (Path.home() / ".comfyui" / "pi-agent").resolve()


def get_live_node_registry() -> dict[str, Any]:
    try:
        import nodes  # type: ignore
        registry = getattr(nodes, "NODE_CLASS_MAPPINGS", {})
        return dict(registry) if isinstance(registry, dict) else {}
    except Exception:
        return {}


def get_model_filenames(category: str) -> list[str]:
    fp = get_folder_paths_module()
    if fp is None:
        return []
    fn = getattr(fp, "get_filename_list", None)
    if not callable(fn):
        return []
    try:
        values = fn(category)
        return sorted(str(v) for v in values)
    except Exception:
        return []
