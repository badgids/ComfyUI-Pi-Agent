from __future__ import annotations
import base64
from pathlib import Path
from typing import Any
from ...compat import get_comfy_user_directory
from ..http_client import request_bytes, request_json


def _image_payload(data:bytes,mime:str,**meta:Any)->dict[str,Any]:
    return {**meta,"mime_type":mime.split(";",1)[0],"base64_data":base64.b64encode(data).decode("ascii"),"size_bytes":len(data)}

async def invoke(name:str,p:dict[str,Any],ctx:Any)->Any:
    if name in {"edit_node_mask","confirm_mask_review","place_chat_image_in_node"}:
        return await ctx.browser.execute(name,p,contract_revision=1,timeout=float(p.get("_timeout_seconds",120) or 120))
    if name=="view_output_image":
        filename=str(p.get("filename") or ""); subfolder=str(p.get("subfolder") or ""); file_type=str(p.get("type") or "output")
        if not filename:
            history=request_json(ctx.base_url,"GET","/history",params={"max_items":int(p.get("history_limit",20) or 20)}); candidates=[]
            for prompt_id,entry in (history.items() if isinstance(history,dict) else []):
                outputs=entry.get("outputs",{}) if isinstance(entry,dict) else {}
                for node_id,node_output in outputs.items():
                    for image in node_output.get("images",[]) if isinstance(node_output,dict) else []:
                        if isinstance(image,dict): candidates.append((prompt_id,node_id,image))
            if not candidates: return {"success":False,"error":"No output image was found in recent ComfyUI history."}
            prompt_id,node_id,image=candidates[-1]; filename=str(image.get("filename") or ""); subfolder=str(image.get("subfolder") or ""); file_type=str(image.get("type") or "output")
        data,mime=request_bytes(ctx.base_url,"GET","/view",params={"filename":filename,"subfolder":subfolder,"type":file_type}); return _image_payload(data,mime,filename=filename,subfolder=subfolder,type=file_type)
    if name=="view_chat_image":
        path=Path(str(p.get("path") or p.get("image_path") or "")).expanduser().resolve(); root=get_comfy_user_directory().resolve()
        try: path.relative_to(root)
        except ValueError: return {"success":False,"error":"Chat image path is outside ComfyUI user data."}
        if not path.is_file(): return {"success":False,"error":"Chat image file does not exist."}
        import mimetypes; return _image_payload(path.read_bytes(),mimetypes.guess_type(path.name)[0] or "application/octet-stream",path=str(path))
    if name=="view_node_mask":
        return await ctx.browser.execute(name,p,contract_revision=1,timeout=60.0)
    raise KeyError(name)
