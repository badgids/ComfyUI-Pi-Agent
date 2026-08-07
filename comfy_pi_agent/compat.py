"""Small compatibility helpers that keep imports safe outside ComfyUI."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def get_folder_paths_module():
    try:
        import folder_paths  # type: ignore
        return folder_paths
    except Exception:
        return None


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
