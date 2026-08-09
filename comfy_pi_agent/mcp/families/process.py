from __future__ import annotations
from typing import Any
from ..http_client import HttpToolError, request_json

async def invoke(name:str,p:dict[str,Any],ctx:Any)->Any:
    if name!="comfy_restart": raise KeyError(name)
    # Never kill an arbitrary process. Use only a runtime-advertised ComfyUI/Manager restart route.
    for method,endpoint in (("POST","/manager/reboot"),("GET","/manager/reboot"),("POST","/api/restart")):
        try: return {"success":True,"endpoint":endpoint,"result":request_json(ctx.base_url,method,endpoint,body={} if method=="POST" else None,timeout=10)}
        except HttpToolError as exc:
            if exc.status not in {404,405}: raise
    return {"success":False,"error":"No verified restart endpoint is available in the current ComfyUI runtime.","error_code":"process_control_unavailable"}
