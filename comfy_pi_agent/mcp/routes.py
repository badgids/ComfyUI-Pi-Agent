from __future__ import annotations

import asyncio
from typing import Any

from .browser_broker import BROWSER_TOOL_BROKER
from .catalog import FL_MCP_COMPAT_TOOL_NAMES, TOOL_SPECS, route_text, search_tools
from .runtime import ToolContext, invoke_tool
from .runtime_context import write_runtime_context
from .security import capability_audit, load_safety_settings

_REGISTERED=False


def _unwrap(value:Any)->dict[str,Any]:
    if not isinstance(value,dict): return {}
    request=value.get("request")
    if isinstance(request,dict) and len(value)==1: return dict(request)
    return dict(value)


def register_mcp_routes()->bool:
    global _REGISTERED
    if _REGISTERED: return True
    try:
        from aiohttp import web  # type: ignore
        from server import PromptServer  # type: ignore
    except Exception:
        return False
    routes=PromptServer.instance.routes

    def base_url(request:Any)->str: return f"{request.scheme}://{request.host}".rstrip("/")

    @routes.get("/pi-agent/mcp/status")
    async def status(request):
        runtime=write_runtime_context(base_url(request))
        return web.json_response({"ok":True,"tool_count":len(FL_MCP_COMPAT_TOOL_NAMES),"dynamic_exposure":True,"browser":BROWSER_TOOL_BROKER.frontend_status(),"runtime":runtime,"safety":capability_audit(load_safety_settings())})

    @routes.get("/pi-agent/mcp/catalog")
    async def catalog(request):
        write_runtime_context(base_url(request))
        return web.json_response({"tool_count":len(FL_MCP_COMPAT_TOOL_NAMES),"tools":[TOOL_SPECS[name].to_dict() for name in FL_MCP_COMPAT_TOOL_NAMES]})

    @routes.post("/pi-agent/mcp/search")
    async def search(request):
        payload=await request.json(); write_runtime_context(base_url(request))
        return web.json_response({"tools":search_tools(str(payload.get("query") or ""),limit=int(payload.get("limit",24) or 24),families=payload.get("families") if isinstance(payload.get("families"),list) else None),"routed_names":route_text(str(payload.get("query") or ""),limit=int(payload.get("limit",24) or 24))})

    @routes.post("/pi-agent/mcp/invoke")
    async def invoke(request):
        payload=await request.json(); current=write_runtime_context(base_url(request)); name=str(payload.get("name") or ""); parameters=_unwrap(payload.get("arguments") if isinstance(payload.get("arguments"),dict) else payload.get("parameters") if isinstance(payload.get("parameters"),dict) else {})
        try:
            result=await invoke_tool(name,parameters,context=ToolContext.current(base_url=str(current.get("base_url") or base_url(request))))
            return web.json_response({"ok":True,"name":name,"result":result})
        except KeyError as exc: return web.json_response({"ok":False,"error":str(exc),"error_code":"unknown_tool"},status=404)
        except asyncio.TimeoutError: return web.json_response({"ok":False,"error":"Tool timed out.","error_code":"timeout"},status=504)
        except Exception as exc:
            return web.json_response({"ok":False,"error":f"{type(exc).__name__}: {exc}","error_code":str(getattr(exc,"code","tool_execution_failed")),"details":getattr(exc,"details",None)},status=409)

    @routes.post("/pi-agent/mcp/browser/hello")
    async def browser_hello(request):
        payload=await request.json(); frontend=BROWSER_TOOL_BROKER.hello(payload if isinstance(payload,dict) else {}); runtime=write_runtime_context(base_url(request),frontend)
        return web.json_response({"ok":True,"browser":frontend,"runtime":runtime})

    @routes.get("/pi-agent/mcp/browser/pending")
    async def browser_pending(request):
        write_runtime_context(base_url(request)); return web.json_response({"request":BROWSER_TOOL_BROKER.claim()})

    @routes.post(r"/pi-agent/mcp/browser/complete/{request_id}")
    async def browser_complete(request):
        try: payload=await request.json()
        except Exception: payload={"success":False,"error":"Browser returned invalid JSON.","error_code":"invalid_browser_result"}
        accepted=BROWSER_TOOL_BROKER.complete(request.match_info["request_id"],payload if isinstance(payload,dict) else {})
        return web.json_response({"ok":bool(accepted)},status=200 if accepted else 404)

    _REGISTERED=True
    return True
