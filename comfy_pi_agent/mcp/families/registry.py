from __future__ import annotations
import json
from typing import Any
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

REGISTRY_BASE="https://api.comfy.org"

def _get(path:str, params:dict[str,Any]|None=None)->Any:
    url=REGISTRY_BASE+path
    if params: url += "?"+urlencode({k:v for k,v in params.items() if v not in (None,"")})
    req=Request(url,headers={"Accept":"application/json","User-Agent":"ComfyUI-Pi-Agent"})
    with urlopen(req,timeout=20) as response: return json.loads(response.read(16*1024*1024).decode("utf-8"))

async def invoke(name:str,p:dict[str,Any],ctx:Any)->Any:
    if name=="registry_search_packages":
        q=str(p.get("query") or "").strip(); limit=max(1,min(int(p.get("limit",20) or 20),100));
        data=_get("/nodes/search",{"search":q,"query":q,"limit":limit,"page":1}) if q else _get("/nodes",{"limit":limit,"page":1})
        return data
    if name=="registry_get_package":
        ident=str(p.get("id") or p.get("node_id") or p.get("package") or "").strip()
        if not ident: return {"success":False,"error":"Package id is required."}
        data=_get("/nodes",{"node_id":ident,"limit":10,"page":1,"latest":"true"}); nodes=data.get("nodes",[]) if isinstance(data,dict) else []
        exact=next((item for item in nodes if str(item.get("id"))==ident), nodes[0] if nodes else None)
        return {"package":exact,"found":exact is not None}
    raise KeyError(name)
