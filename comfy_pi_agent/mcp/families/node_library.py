from __future__ import annotations
from typing import Any
from ..node_catalog import NodeCatalogStore, catalog_contract_hash, classify_node_origin, fetch_live_catalog, node_schema_hash

async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    store=NodeCatalogStore()
    try:
        if name == "node_knowledge_search":
            return {"results":store.search(str(p.get("query") or ""), int(p.get("limit",20) or 20)), "status":store.status(), "authority":"discovery-only"}
        catalog=fetch_live_catalog(ctx.base_url)
        reconciliation=store.reconcile(catalog, source=ctx.base_url+"/object_info")
        if name == "node_library_status":
            counts={}
            for info in catalog.values():
                if isinstance(info,dict):
                    origin=classify_node_origin(info); counts[origin]=counts.get(origin,0)+1
            return {"state":"fresh","node_count":len(catalog),"catalog_hash":catalog_contract_hash(catalog),"origin_counts":counts,"reconciliation":reconciliation,"persistent":store.status()}
        if name == "node_library_search":
            q=str(p.get("query") or p.get("search") or "").lower(); limit=max(1,min(int(p.get("limit",50) or 50),500)); results=[]
            for node_type,info in catalog.items():
                if not isinstance(info,dict): continue
                hay=" ".join((str(node_type),str(info.get('display_name') or ''),str(info.get('category') or ''),str(info.get('description') or ''))).lower()
                if not q or q in hay: results.append({"node_type":node_type,"display_name":info.get("display_name",node_type),"category":info.get("category",""),"description":info.get("description",""),"origin":classify_node_origin(info),"schema_hash":node_schema_hash(str(node_type),info)})
                if len(results)>=limit: break
            return {"results":results,"count":len(results),"catalog_hash":catalog_contract_hash(catalog)}
        node_type=str(p.get("node_type") or p.get("type") or "")
        if name == "node_library_get_details":
            info=catalog.get(node_type)
            if not isinstance(info,dict): return {"success":False,"error":f"Node type {node_type!r} is not loaded."}
            return {"node_type":node_type,"schema":info,"schema_hash":node_schema_hash(node_type,info),"origin":classify_node_origin(info),"catalog_hash":catalog_contract_hash(catalog)}
        if name == "node_library_find_compatible":
            info=catalog.get(node_type)
            if not isinstance(info,dict): return {"success":False,"error":f"Node type {node_type!r} is not loaded."}
            direction=str(p.get("direction") or "downstream"); desired=set(map(str, info.get("output",[]) if direction=="downstream" else [spec[0] for group in (info.get('input') or {}).values() if isinstance(group,dict) for spec in group.values() if isinstance(spec,list) and spec and isinstance(spec[0],str)])); matches=[]
            for other,oinfo in catalog.items():
                if not isinstance(oinfo,dict) or other==node_type: continue
                types=set(map(str,[spec[0] for group in (oinfo.get('input') or {}).values() if isinstance(group,dict) for spec in group.values() if isinstance(spec,list) and spec and isinstance(spec[0],str)] if direction=="downstream" else oinfo.get("output",[])))
                overlap=sorted(desired & types)
                if overlap: matches.append({"node_type":other,"types":overlap,"display_name":oinfo.get("display_name",other)})
            return {"node_type":node_type,"direction":direction,"results":matches[:max(1,min(int(p.get('limit',50) or 50),500))]}
        raise KeyError(name)
    finally: store.close()
