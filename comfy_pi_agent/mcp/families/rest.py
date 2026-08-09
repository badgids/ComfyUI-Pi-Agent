from __future__ import annotations
import base64
import json
from pathlib import Path
from typing import Any

from ...compat import get_comfy_search_path_registry, get_comfy_user_directory
from ..http_client import HttpToolError, request_bytes, request_json, upload_file

ERROR_BUFFER: list[dict[str, Any]] = []


def _record_error(name: str, exc: Exception) -> None:
    ERROR_BUFFER.append({"tool": name, "error": f"{type(exc).__name__}: {exc}"})
    del ERROR_BUFFER[:-100]


def _approved_file(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    roots = [get_comfy_user_directory()]
    for paths in get_comfy_search_path_registry(existing_only=False).values(): roots.extend(paths)
    for root in roots:
        try: candidate.relative_to(Path(root).expanduser().resolve()); return candidate
        except ValueError: pass
    raise ValueError("File is outside the running ComfyUI registered/user roots.")

async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    try:
        if name == "comfy_status":
            try: stats = request_json(ctx.base_url, "GET", "/system_stats", timeout=5.0)
            except Exception as exc: return {"reachable": False, "error": str(exc)}
            return {"reachable": True, "system_stats": stats}
        if name == "comfy_get_logs":
            # ComfyUI core does not expose a universal log endpoint. Use a verified endpoint if present.
            for endpoint in ("/internal/logs/raw", "/logs"):
                try: return {"endpoint": endpoint, "data": request_json(ctx.base_url, "GET", endpoint, timeout=5.0)}
                except HttpToolError as exc:
                    if exc.status != 404: raise
            return {"success": False, "error": "No supported ComfyUI log HTTP endpoint is available in this runtime."}
        if name == "comfy_jobs_list": return request_json(ctx.base_url, "GET", "/api/jobs", params={k:v for k,v in p.items() if v is not None})
        if name == "comfy_job_get": return request_json(ctx.base_url, "GET", f"/api/jobs/{p.get('job_id') or p.get('id')}")
        if name == "comfy_free_memory": return request_json(ctx.base_url, "POST", "/free", body={k:v for k,v in p.items() if not k.startswith('_')})
        if name == "comfy_history_delete":
            body = {"clear": True} if p.get("clear_all") else {"delete": p.get("prompt_ids") or p.get("ids") or []}
            return request_json(ctx.base_url, "POST", "/history", body=body)
        if name == "comfy_settings_get":
            ident = p.get("id"); return request_json(ctx.base_url, "GET", f"/settings/{ident}" if ident else "/settings")
        if name == "comfy_settings_set":
            ident = p.get("id"); return request_json(ctx.base_url, "POST", f"/settings/{ident}" if ident else "/settings", body=p.get("value") if ident else p.get("settings", p))
        if name == "delete_queue_items":
            if p.get("interrupt"): request_json(ctx.base_url, "POST", "/interrupt", body={})
            if p.get("clear_all"): return request_json(ctx.base_url, "POST", "/queue", body={"clear": True})
            return request_json(ctx.base_url, "POST", "/queue", body={"delete": p.get("prompt_ids") or p.get("ids") or []})
        if name == "get_execution_history":
            prompt_id = p.get("prompt_id"); return request_json(ctx.base_url, "GET", f"/history/{prompt_id}" if prompt_id else "/history", params={"max_items": p.get("max_items")} if p.get("max_items") else None)
        if name == "get_queue_status_details":
            return {"queue": request_json(ctx.base_url, "GET", "/queue"), "history": request_json(ctx.base_url, "GET", "/history", params={"max_items": int(p.get('history_limit', 20) or 20)})}
        if name == "get_execution_details":
            prompt_id = str(p.get("prompt_id") or p.get("id") or ""); return {"prompt_id": prompt_id, "history": request_json(ctx.base_url, "GET", f"/history/{prompt_id}"), "queue": request_json(ctx.base_url, "GET", "/queue")}
        if name == "clear_error_buffer": ERROR_BUFFER.clear(); return {"success": True, "cleared": True}
        if name == "comfy_models_list":
            folder = str(p.get("folder") or ""); endpoint = f"/experiment/models/{folder}" if folder else "/experiment/models"; return request_json(ctx.base_url, "GET", endpoint)
        if name == "comfy_workflow_templates_list":
            pack, filename = p.get("pack"), p.get("filename"); endpoint = f"/api/workflow_templates/{pack}/{filename}" if pack and filename else "/workflow_templates"; return request_json(ctx.base_url, "GET", endpoint)
        if name == "comfy_global_subgraphs_list":
            ident = p.get("id"); return request_json(ctx.base_url, "GET", f"/global_subgraphs/{ident}" if ident else "/global_subgraphs")
        if name == "comfy_node_replacements_get": return request_json(ctx.base_url, "GET", "/node_replacements")
        if name == "comfy_assets_list": return request_json(ctx.base_url, "GET", "/api/assets", params={k:v for k,v in p.items() if v is not None})
        if name == "comfy_asset_get": return request_json(ctx.base_url, "GET", f"/api/assets/{p.get('asset_id') or p.get('id')}")
        if name == "comfy_tags_list": return request_json(ctx.base_url, "GET", "/api/tags", params={k:v for k,v in p.items() if v is not None})
        if name in {"comfy_asset_upload", "comfy_assets_upload"}:
            path = _approved_file(str(p.get("file_path") or p.get("path") or "")); fields = {k:v for k,v in p.items() if k not in {"file_path","path"}}; return upload_file(ctx.base_url, "/api/assets", path, field="file", fields=fields)
        if name in {"comfy_upload_image", "comfy_upload_mask"}:
            path = _approved_file(str(p.get("image_path") or p.get("mask_path") or p.get("path") or "")); endpoint = "/upload/mask" if name.endswith("mask") else "/upload/image"; fields = {k:v for k,v in p.items() if k not in {"image_path","mask_path","path"}}; return upload_file(ctx.base_url, endpoint, path, field="image", fields=fields)
        if name == "comfy_list_folders":
            category = str(p.get("folder_type") or p.get("category") or ""); registry = get_comfy_search_path_registry(existing_only=True); roots = registry.get(category, []) if category else [root for values in registry.values() for root in values]
            pattern = str(p.get("pattern") or "").lower(); limit = max(1, min(int(p.get("limit", 500) or 500), 5000)); items=[]
            for root in roots:
                if not Path(root).is_dir(): continue
                for path in Path(root).rglob("*"):
                    if pattern and pattern not in str(path).lower(): continue
                    items.append({"path": str(path), "name": path.name, "is_dir": path.is_dir(), "size": path.stat().st_size if path.is_file() else 0});
                    if len(items) >= limit: break
                if len(items)>=limit: break
            return {"items": items, "count": len(items), "roots": [str(x) for x in roots]}
        if name == "comfy_read_file":
            path = _approved_file(str(p.get("path") or p.get("file_path") or "")); max_bytes=max(1,min(int(p.get("max_bytes", 2_000_000) or 2_000_000),16_000_000)); raw=path.read_bytes()[:max_bytes];
            try: text=raw.decode("utf-8"); return {"path":str(path),"text":text,"truncated":path.stat().st_size>len(raw)}
            except UnicodeDecodeError: return {"path":str(path),"base64":base64.b64encode(raw).decode(),"truncated":path.stat().st_size>len(raw)}
        if name == "comfy_search_resources":
            query=str(p.get("query") or p.get("pattern") or "").lower(); category=str(p.get("folder_type") or p.get("category") or ""); registry=get_comfy_search_path_registry(existing_only=True); roots=registry.get(category,[]) if category else [r for values in registry.values() for r in values]; limit=max(1,min(int(p.get("limit",100) or 100),1000)); results=[]
            for root in roots:
                for path in Path(root).rglob("*"):
                    if query in path.name.lower(): results.append(str(path))
                    if len(results)>=limit: break
                if len(results)>=limit: break
            return {"results":results,"count":len(results)}
        if name == "extract_workflow_from_image":
            path=_approved_file(str(p.get("path") or p.get("image_path") or "")); raw=path.read_bytes();
            # PNG text chunks can be extracted without Pillow. Search bounded UTF-8 metadata for workflow/prompt JSON.
            text=raw.decode("latin1", errors="ignore"); found={}
            for key in ("workflow", "prompt"):
                marker=key+"\x00"; index=text.find(marker)
                if index>=0:
                    value=text[index+len(marker):].split("\x00",1)[0]
                    try: found[key]=json.loads(value.encode("latin1").decode("utf-8"))
                    except Exception: pass
            return {"path":str(path),**found,"found":bool(found)}
        raise KeyError(name)
    except Exception as exc:
        _record_error(name, exc); raise
