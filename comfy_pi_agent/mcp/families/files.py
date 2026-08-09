from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any
from ...compat import get_comfy_workflow_roots


def _roots() -> list[Path]:
    roots = get_comfy_workflow_roots(existing_only=False)
    for root in roots: root.mkdir(parents=True, exist_ok=True)
    return roots


def _safe(path_value: str) -> Path:
    raw = Path(str(path_value or ""))
    for root in _roots():
        candidate = raw if raw.is_absolute() else root / raw
        try: resolved = candidate.expanduser().resolve()
        except Exception: continue
        try: resolved.relative_to(root.expanduser().resolve()); return resolved
        except ValueError: continue
    raise ValueError("Workflow path is outside the running ComfyUI workflow roots.")

async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    if name == "workflow_list_files":
        files = []
        for root in _roots():
            if root.is_dir(): files.extend(str(path) for path in root.rglob("*.json") if path.is_file())
        return {"files": sorted(set(files)), "roots": [str(root) for root in _roots()]}
    if name == "workflow_read_file":
        path = _safe(str(p.get("path") or p.get("filename") or "")); return {"path": str(path), "workflow": json.loads(path.read_text(encoding="utf-8"))}
    if name == "workflow_save_current":
        path = _safe(str(p.get("path") or p.get("filename") or "workflow.json")); path.parent.mkdir(parents=True, exist_ok=True)
        current = await ctx.browser.execute("workflow_get_current_json", {"format": "workflow"}, contract_revision=2)
        workflow = current.get("workflow") if isinstance(current, dict) else current
        tmp = path.with_suffix(path.suffix + ".tmp"); tmp.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"); os.replace(tmp, path)
        return {"success": True, "path": str(path)}
    if name == "workflow_rename_file":
        source = _safe(str(p.get("path") or p.get("source") or "")); target = _safe(str(p.get("new_path") or p.get("target") or "")); target.parent.mkdir(parents=True, exist_ok=True); os.replace(source, target); return {"success": True, "path": str(target)}
    if name == "workflow_delete_file":
        path = _safe(str(p.get("path") or p.get("filename") or "")); path.unlink(); return {"success": True, "path": str(path)}
    raise KeyError(name)
