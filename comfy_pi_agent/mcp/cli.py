from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .catalog import FL_MCP_COMPAT_TOOL_NAMES, TOOL_SPECS, family_tools, route_text, search_tools
from .http_client import request_json
from .runtime_context import current_base_url


def _json_arg(value:str)->dict[str,Any]:
    if not value: return {}
    loaded=json.loads(value)
    if not isinstance(loaded,dict): raise ValueError("Arguments must be a JSON object.")
    return loaded


def _base_url() -> str:
    config_path = os.getenv("COMFYUI_PI_BRIDGE_CONFIG", "").strip()
    if config_path:
        try:
            data = json.loads(Path(config_path).read_text(encoding="utf-8"))
            value = str(data.get("comfyui_base_url") or "").rstrip("/") if isinstance(data, dict) else ""
            if value:
                return value
        except Exception:
            pass
    return current_base_url()

def invoke_remote(name:str, arguments:dict[str,Any])->Any:
    base=_base_url()
    response=request_json(base,"POST","/pi-agent/mcp/invoke",body={"name":name,"arguments":arguments},timeout=float(arguments.get("_timeout_seconds",180) or 180)+10)
    if not isinstance(response,dict) or not response.get("ok"):
        raise RuntimeError(str((response or {}).get("error") if isinstance(response,dict) else response))
    return response.get("result")


def main()->None:
    parser=argparse.ArgumentParser(description="ComfyUI-Pi dynamic MCP tool bridge")
    sub=parser.add_subparsers(dest="command",required=True)
    p_search=sub.add_parser("search"); p_search.add_argument("query"); p_search.add_argument("--limit",type=int,default=24)
    p_route=sub.add_parser("route-text"); p_route.add_argument("text"); p_route.add_argument("--limit",type=int,default=24)
    p_catalog=sub.add_parser("catalog"); p_catalog.add_argument("--family",default="")
    p_invoke=sub.add_parser("invoke"); p_invoke.add_argument("name"); p_invoke.add_argument("--arguments",default="{}")
    args=parser.parse_args()
    if args.command=="search": result={"tools":search_tools(args.query,limit=args.limit)}
    elif args.command=="route-text": result={"names":route_text(args.text,limit=args.limit)}
    elif args.command=="catalog":
        specs=family_tools(args.family) if args.family else [TOOL_SPECS[name] for name in FL_MCP_COMPAT_TOOL_NAMES]; result={"tools":[spec.to_dict() for spec in specs]}
    else: result=invoke_remote(args.name,_json_arg(args.arguments))
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__": main()
