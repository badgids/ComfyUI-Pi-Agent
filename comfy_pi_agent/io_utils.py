from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .compat import get_comfy_user_directory

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(value: str, fallback: str = "project") -> str:
    cleaned = _SAFE_NAME.sub("-", value.strip()).strip("-._")
    return cleaned or fallback


def resolve_output_root(requested: str | None, namespace: str = "projects") -> Path:
    if requested and requested.strip():
        root = Path(requested).expanduser()
        if not root.is_absolute():
            root = get_comfy_user_directory() / "pi-agent" / root
    else:
        root = get_comfy_user_directory() / "pi-agent" / namespace
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_join(root: Path, *parts: str) -> Path:
    target = root.joinpath(*parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Refusing path outside output root: {target}") from exc
    return target


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


def atomic_write_json(path: Path, payload: Any) -> Path:
    return atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_json(value: str | dict | list, default: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return default
    path = Path(text).expanduser()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(text)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)
