from __future__ import annotations
import os
import py_compile
import re
import subprocess
from pathlib import Path
from typing import Any
from ...compat import get_comfy_search_paths


def _roots()->list[Path]: return [Path(p).expanduser().resolve() for p in get_comfy_search_paths("custom_nodes",existing_only=False)]

def _resolve(value:str, *, must_exist:bool=False)->Path:
    raw=Path(str(value or ""))
    for root in _roots():
        candidate=(raw if raw.is_absolute() else root/raw).expanduser().resolve()
        try: candidate.relative_to(root)
        except ValueError: continue
        if must_exist and not candidate.exists(): continue
        return candidate
    raise ValueError("Path is outside every live registered custom_nodes root.")

def _run(args:list[str],cwd:Path,timeout:int=120)->dict[str,Any]:
    proc=subprocess.run(args,cwd=str(cwd),capture_output=True,text=True,timeout=timeout,check=False)
    return {"returncode":proc.returncode,"stdout":proc.stdout[-200000:],"stderr":proc.stderr[-200000:],"ok":proc.returncode==0}

async def invoke(name:str,p:dict[str,Any],ctx:Any)->Any:
    if name=="custom_nodes_list_packs":
        packs=[]
        for root in _roots():
            if root.is_dir():
                packs.extend({"name":x.name,"path":str(x),"root":str(root)} for x in root.iterdir() if x.is_dir())
        return {"roots":[str(r) for r in _roots()],"packs":packs,"count":len(packs)}
    if name in {"custom_nodes_read_file","custom_nodes_read_file_excerpt"}:
        path=_resolve(str(p.get("path") or ""),must_exist=True); start=max(1,int(p.get("start_line",1) or 1)); count=max(1,min(int(p.get("line_count",200) or 200),5000)); lines=path.read_text(encoding="utf-8",errors="replace").splitlines(); return {"path":str(path),"start_line":start,"lines":lines[start-1:start-1+count],"total_lines":len(lines)}
    if name=="custom_nodes_search":
        base=_resolve(str(p.get("path") or "."),must_exist=True); query=str(p.get("query") or ""); limit=max(1,min(int(p.get("max_results",100) or 100),1000)); results=[]
        rg=__import__('shutil').which('rg')
        if rg:
            out=_run([rg,"--line-number","--no-heading","--color","never",query,str(base)],base,60); return {**out,"results":out["stdout"].splitlines()[:limit]}
        for path in base.rglob("*"):
            if not path.is_file() or path.stat().st_size>2_000_000: continue
            try: lines=path.read_text(encoding="utf-8",errors="ignore").splitlines()
            except OSError: continue
            for index,line in enumerate(lines,1):
                if query.lower() in line.lower(): results.append({"path":str(path),"line":index,"text":line[:1000]})
                if len(results)>=limit: return {"results":results,"count":len(results)}
        return {"results":results,"count":len(results)}
    if name=="custom_nodes_write_file":
        path=_resolve(str(p.get("path") or "")); overwrite=bool(p.get("overwrite"));
        if path.exists() and not overwrite: return {"success":False,"error":"File exists; set overwrite=true."}
        path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(str(p.get("content") or ""),encoding="utf-8"); os.replace(tmp,path); return {"success":True,"path":str(path)}
    if name=="custom_nodes_apply_patch":
        patch=str(p.get("patch") or "");
        if not patch.strip(): return {"success":False,"error":"Patch text is required."}
        touched=[]
        for match in re.finditer(r"^(?:\+\+\+|---)\s+(?:a/|b/)?([^\t\n]+)",patch,re.M):
            value=match.group(1).strip()
            if value!="/dev/null": touched.append(_resolve(value))
        roots=_roots(); cwd=roots[0] if roots else None
        if not cwd: return {"success":False,"error":"No live custom_nodes root is registered."}
        checked=subprocess.run(["git","apply","--check","--whitespace=error-all","-"],cwd=str(cwd),input=patch,text=True,capture_output=True,timeout=120,check=False)
        if checked.returncode != 0:
            return {"success":False,"checked":False,"returncode":checked.returncode,"stdout":checked.stdout,"stderr":checked.stderr,"touched":[str(x) for x in touched]}
        proc=subprocess.run(["git","apply","--whitespace=error-all","-"],cwd=str(cwd),input=patch,text=True,capture_output=True,timeout=120,check=False)
        return {"success":proc.returncode==0,"checked":True,"returncode":proc.returncode,"stdout":proc.stdout,"stderr":proc.stderr,"touched":[str(x) for x in touched]}
    if name=="custom_nodes_create_pack":
        name_value=re.sub(r"[^A-Za-z0-9._-]+","-",str(p.get("name") or p.get("pack_name") or "comfyui-pi-pack")).strip("-"); root=_roots()[0] if _roots() else None
        if root is None: return {"success":False,"error":"No live custom_nodes root is registered."}
        pack=(root/name_value).resolve(); pack.relative_to(root); pack.mkdir(parents=True,exist_ok=bool(p.get("overwrite"))); init=pack/"__init__.py"
        if not init.exists() or p.get("overwrite"): init.write_text('NODE_CLASS_MAPPINGS = {}\nNODE_DISPLAY_NAME_MAPPINGS = {}\n',encoding="utf-8")
        return {"success":True,"path":str(pack)}
    if name=="custom_nodes_validate_pack":
        base=_resolve(str(p.get("path") or "."),must_exist=True); failures=[]; checked=0
        for path in base.rglob("*.py"):
            checked+=1
            try: py_compile.compile(str(path),doraise=True)
            except py_compile.PyCompileError as exc: failures.append({"path":str(path),"error":str(exc)})
        return {"success":not failures,"checked":checked,"failures":failures}
    if name in {"custom_nodes_git_status","custom_nodes_git_diff","custom_nodes_git_commit","custom_nodes_git_push"}:
        base=_resolve(str(p.get("path") or "."),must_exist=True); cwd=base if base.is_dir() else base.parent
        if name == "custom_nodes_git_commit":
            staged=_run(["git","add","-A","--"],cwd)
            if not staged.get("success"):
                return staged
            return _run(["git","commit","-m",str(p.get("message") or "ComfyUI-Pi update")],cwd)
        args={"custom_nodes_git_status":["git","status","--short"],"custom_nodes_git_diff":["git","diff","--"],"custom_nodes_git_push":["git","push"]}[name]
        return _run(args,cwd)
    raise KeyError(name)
