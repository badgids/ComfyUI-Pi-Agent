from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..compat import get_comfy_search_path_registry, get_comfy_user_directory, get_folder_paths_module


def runtime_context_path() -> Path:
    override = os.getenv("COMFYUI_PI_MCP_RUNTIME_FILE", "").strip()
    path = Path(override).expanduser() if override else get_comfy_user_directory() / "pi-agent" / "mcp" / "runtime.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _runtime_directory(name: str) -> str:
    fp = get_folder_paths_module()
    if fp is None:
        return ""
    fn = getattr(fp, f"get_{name}_directory", None)
    if callable(fn):
        try:
            return str(Path(fn()).expanduser().resolve())
        except Exception:
            return ""
    return ""


def runtime_paths_snapshot() -> dict[str, Any]:
    registry = get_comfy_search_path_registry(existing_only=False)
    return {
        "user": str(get_comfy_user_directory()),
        "input": _runtime_directory("input"),
        "output": _runtime_directory("output"),
        "temp": _runtime_directory("temp"),
        "search_paths": {key: [str(path) for path in values] for key, values in registry.items()},
    }


def write_runtime_context(base_url: str = "", frontend: dict[str, Any] | None = None) -> dict[str, Any]:
    current = read_runtime_context()
    value = {
        **current,
        "updated_at": time.time(),
        "base_url": str(base_url or current.get("base_url") or "").rstrip("/"),
        "paths": runtime_paths_snapshot(),
    }
    if frontend is not None:
        value["frontend"] = frontend
    path = runtime_context_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)
    return value


def read_runtime_context() -> dict[str, Any]:
    override = os.getenv("COMFYUI_PI_BASE_URL", "").strip().rstrip("/")
    data: dict[str, Any] = {}
    path = runtime_context_path()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    if override:
        data["base_url"] = override
    return data


def current_base_url(required: bool = True) -> str:
    value = str(read_runtime_context().get("base_url") or "").rstrip("/")
    if required and not value:
        raise RuntimeError(
            "The current ComfyUI base URL is unknown. Open the running ComfyUI web UI once "
            "or set COMFYUI_PI_BASE_URL for an explicit non-browser client."
        )
    return value


def runtime_path_environment() -> dict[str, str]:
    """Export authoritative running-ComfyUI paths to supervised child processes."""
    payload = runtime_paths_snapshot()
    return {
        "COMFYUI_PI_RUNTIME_PATHS_JSON": json.dumps(payload, ensure_ascii=False),
        "COMFYUI_PI_MCP_RUNTIME_FILE": str(runtime_context_path()),
    }
