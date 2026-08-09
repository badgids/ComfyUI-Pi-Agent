from __future__ import annotations
from typing import Any
from ..http_client import HttpToolError, request_json


def _probe(ctx:Any)->dict[str,Any]:
    version="unknown"
    try:
        data=request_json(ctx.base_url,"GET","/manager/version",timeout=5); version=str(data.get("version") or data.get("data") or data)
    except HttpToolError as exc:
        if exc.status not in {404,405}: raise
    for protocol,endpoint in (("unversioned","/manager/queue/status"),("v2","/v2/manager/queue/status")):
        try:
            queue=request_json(ctx.base_url,"GET",endpoint,timeout=5); return {"installed":True,"version":version,"protocol":protocol,"queue":queue}
        except HttpToolError as exc:
            if exc.status not in {404,405}: raise
    return {"installed":bool(version!="unknown"),"version":version,"protocol":"","queue":None}


def _fallback(ctx:Any, method:str, endpoints:list[str], *, params=None, body=None)->Any:
    last=None
    for endpoint in endpoints:
        try: return request_json(ctx.base_url,method,endpoint,params=params,body=body,timeout=30)
        except HttpToolError as exc:
            last=exc
            if exc.status not in {404,405}: raise
    if last: raise last
    raise RuntimeError("No Manager endpoint candidates supplied.")

async def invoke(name:str,p:dict[str,Any],ctx:Any)->Any:
    status=_probe(ctx)
    if name in {"manager_v4_status"}: return status
    if name in {"manager_queue_status","manager_v4_queue_status"}: return status.get("queue") or _fallback(ctx,"GET",["/manager/queue/status","/v2/manager/queue/status"])
    if name in {"manager_queue_start"}: return _fallback(ctx,"POST",["/manager/queue/start"],body={}) if status.get("protocol")=="unversioned" else _fallback(ctx,"GET",["/v2/manager/queue/start"])
    if name in {"manager_queue_reset"}: return _fallback(ctx,"POST",["/manager/queue/reset"],body={}) if status.get("protocol")=="unversioned" else _fallback(ctx,"GET",["/v2/manager/queue/reset"])
    if name=="manager_v4_installed_packs": return _fallback(ctx,"GET",["/v2/customnode/installed","/customnode/installed"],params={"mode":p.get("mode","default")})
    if name=="manager_v4_snapshots": return _fallback(ctx,"GET",["/v2/snapshot/getlist","/snapshot/getlist"])
    if name in {"manager_v4_node_mappings","manager_get_node_mappings"}: return _fallback(ctx,"GET",["/v2/customnode/getmappings","/customnode/getmappings"],params={"mode":p.get("mode","local")})
    if name in {"manager_v4_external_models","manager_search_external_models"}: return _fallback(ctx,"GET",["/v2/externalmodel/getlist","/externalmodel/getlist"],params={"mode":p.get("mode","cache")})
    if name=="manager_search_nodes":
        data=_fallback(ctx,"GET",["/v2/customnode/getlist","/customnode/getlist"],params={"mode":p.get("mode","cache")}); q=str(p.get("query") or "").lower(); items=data if isinstance(data,dict) else {}; results=[]
        for key,value in items.items():
            hay=(str(key)+" "+str(value)).lower()
            if not q or q in hay: results.append({"id":key,"data":value})
        return {"results":results[:max(1,min(int(p.get('max_results',20) or 20),200))],"count":len(results)}
    if name=="manager_check_updates": return _fallback(ctx,"GET",["/customnode/getlist","/v2/customnode/getlist"],params={"mode":"local","skip_update":"false"})
    if name in {"manager_queue_action","manager_v4_queue_action"}:
        action=str(p.get("action") or "").strip().lower(); payload=p.get("payload") if isinstance(p.get("payload"),dict) else p
        if status.get("protocol")=="v2": return request_json(ctx.base_url,"POST","/v2/manager/queue/task",body={"action":action,**payload})
        route={"install":"/manager/queue/install","update":"/manager/queue/update","uninstall":"/manager/queue/uninstall","disable":"/manager/queue/disable","enable":"/manager/queue/enable"}.get(action)
        if not route: return {"success":False,"error":f"Unsupported Manager action: {action}"}
        return request_json(ctx.base_url,"POST",route,body=payload)
    raise KeyError(name)
