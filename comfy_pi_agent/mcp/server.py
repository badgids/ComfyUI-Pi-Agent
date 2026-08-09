"""Dependency-free MCP stdio adapter with a dynamically exposed FL-MCP-compatible tool surface."""
from __future__ import annotations
import json
import os
import sys
from typing import Any

from .catalog import FL_MCP_COMPAT_TOOL_NAMES, TOOL_SPECS, family_tools, search_tools, tool_input_schema
from .cli import invoke_remote

PROTOCOL_VERSION="2026-07-28"
LEGACY_PROTOCOL_VERSION="2025-11-25"
META_NAMES=("comfyui_tool_search","comfyui_tool_activate","comfyui_tool_call")


def _tool(name:str)->dict[str,Any]:
    if name=="comfyui_tool_search": return {"name":name,"description":"Search the complete ComfyUI-Pi FL-MCP compatibility catalog without exposing all tools to the model.","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":128}},"required":["query"]}}
    if name=="comfyui_tool_activate": return {"name":name,"description":"Activate exact FL-MCP-compatible tool names or one tool family for this MCP session, then refresh tools/list.","inputSchema":{"type":"object","properties":{"names":{"type":"array","items":{"type":"string"}},"family":{"type":"string"}}}}
    if name=="comfyui_tool_call": return {"name":name,"description":"Immediately call any exact FL-MCP-compatible tool by name. Useful after discovery in the same model turn.","inputSchema":{"type":"object","properties":{"name":{"type":"string"},"arguments":{"type":"object"}},"required":["name"]}}
    spec=TOOL_SPECS[name]
    return {"name":name,"description":spec.description+" Accepts FL-MCP-style {request:{...}} or direct object arguments.","inputSchema":tool_input_schema(name),"annotations":{"readOnlyHint":spec.risk=="read_only","destructiveHint":spec.risk=="approval_required"}}


class DynamicMcpServer:
    def __init__(self, send=None) -> None:
        self.expose=str(os.getenv("COMFYUI_PI_MCP_EXPOSE","dynamic")).lower()
        self.active=set(FL_MCP_COMPAT_TOOL_NAMES if self.expose=="all" else ("mcp_capability_audit",))
        self.legacy_session=False
        self.send=send or self._stdout

    @staticmethod
    def _stdout(message:dict[str,Any])->None:
        sys.stdout.write(json.dumps(message,ensure_ascii=False,separators=(",",":"))+"\n"); sys.stdout.flush()

    def notify_changed(self)->None:
        if self.legacy_session:
            self.send({"jsonrpc":"2.0","method":"notifications/tools/list_changed"})

    def list_tools(self)->list[dict[str,Any]]:
        # MCP 2026-07-28 is stateless: keep tools/list deterministic/cacheable.
        # Legacy clients may opt into the older changing list after initialize.
        visible = sorted(self.active) if (self.legacy_session or self.expose == "all") else ["mcp_capability_audit"]
        return [_tool(name) for name in (*META_NAMES,*visible)]

    def activate(self,names:list[str]|None=None,family:str="")->list[str]:
        requested=list(names or [])
        if family: requested.extend(spec.name for spec in family_tools(family))
        unknown=[name for name in requested if name not in TOOL_SPECS]
        if unknown: raise ValueError("Unknown ComfyUI-Pi tool(s): "+", ".join(unknown))
        before=set(self.active); self.active.update(requested)
        if self.active!=before: self.notify_changed()
        return sorted(set(requested))

    def call(self,name:str,args:dict[str,Any])->Any:
        if name=="comfyui_tool_search": return {"tools":search_tools(str(args.get("query") or ""),limit=int(args.get("limit",24) or 24))}
        if name=="comfyui_tool_activate": return {"activated":self.activate(list(args.get("names") or []),str(args.get("family") or "")),"active_count":len(self.active)}
        if name=="comfyui_tool_call":
            target=str(args.get("name") or ""); call_args=args.get("arguments") if isinstance(args.get("arguments"),dict) else {}
            if target not in TOOL_SPECS: raise ValueError(f"Unknown ComfyUI-Pi tool: {target}")
            if target not in self.active: self.activate([target])
            return invoke_remote(target,call_args)
        if name not in TOOL_SPECS: raise ValueError(f"Unknown tool: {name}")
        if name not in self.active:
            # Exact hidden names stay callable in stateless MCP. Only a legacy initialized
            # client gets a changing tools/list notification.
            self.activate([name])
        if isinstance(args.get("request"),dict) and len(args)==1: args=dict(args["request"])
        return invoke_remote(name,args)

    def handle(self,message:dict[str,Any])->None:
        method=str(message.get("method") or ""); ident=message.get("id")
        if method=="notifications/initialized": return
        try:
            if method=="initialize":
                # Backward compatibility for 2025-era MCP clients. Latest 2026 clients
                # do not initialize; they may call server/discover or tools/list directly.
                self.legacy_session=True
                result={"protocolVersion":LEGACY_PROTOCOL_VERSION,"capabilities":{"tools":{"listChanged":True}},"serverInfo":{"name":"comfyui-pi-agent","version":"dynamic-fl-mcp-compat-v1"}}
            elif method=="server/discover":
                result={"protocolVersion":PROTOCOL_VERSION,"serverInfo":{"name":"comfyui-pi-agent","version":"dynamic-fl-mcp-compat-v1"},"capabilities":{"tools":{}},"extensions":{"io.comfyui-pi/dynamic-tools":{"version":"1","tool_count":len(FL_MCP_COMPAT_TOOL_NAMES),"meta_tools":list(META_NAMES)}}}
            elif method=="ping": result={}
            elif method=="tools/list": result={"tools":self.list_tools()}
            elif method=="tools/call":
                params=message.get("params") if isinstance(message.get("params"),dict) else {}; name=str(params.get("name") or ""); args=params.get("arguments") if isinstance(params.get("arguments"),dict) else {}; data=self.call(name,args); result={"content":[{"type":"text","text":json.dumps(data,ensure_ascii=False,indent=2)}],"structuredContent":data if isinstance(data,dict) else {"result":data},"isError":False}
            else: raise KeyError(f"Method not found: {method}")
            if ident is not None: self.send({"jsonrpc":"2.0","id":ident,"result":result})
        except Exception as exc:
            if ident is not None: self.send({"jsonrpc":"2.0","id":ident,"error":{"code":-32000,"message":f"{type(exc).__name__}: {exc}"}})


def main()->None:
    server=DynamicMcpServer()
    for line in sys.stdin:
        if not line.strip(): continue
        try: message=json.loads(line)
        except Exception as exc:
            print(f"Invalid MCP JSON: {exc}",file=sys.stderr); continue
        if isinstance(message,dict): server.handle(message)

if __name__=="__main__": main()
