from __future__ import annotations

import asyncio

from .chat import CHAT_MANAGER
from .models import inventory_models
from .pi_runtime import discover_pi
from .tutorials import compile_tutorial
from .version import __version__
from .workflow import analyze_workflow
from .integrations.router import (
    build_dynamic_integration_context,
    integration_status,
    load_integration_module,
    load_integration_registry,
)


def _integration_entry(integration_id: str):
    for entry in load_integration_registry().get("integrations", []):
        if isinstance(entry, dict) and entry.get("id") == integration_id:
            return entry
    raise KeyError(f"Unknown integration: {integration_id}")


def _minimax_h3():
    return load_integration_module(_integration_entry("minimax-h3-director"))


def _whatdreamscost():
    return load_integration_module(_integration_entry("whatdreamscost-comfyui"))


def _scene_camera_action():
    return load_integration_module(_integration_entry("scene-camera-action"))


def _minimax_h3_turbo():
    return load_integration_module(_integration_entry("minimax-h3-turbo"))

_REGISTERED = False


def register_routes() -> bool:
    global _REGISTERED
    if _REGISTERED:
        return True
    try:
        from aiohttp import web  # type: ignore
        from server import PromptServer  # type: ignore
    except Exception:
        return False

    routes = PromptServer.instance.routes

    @routes.get("/pi-agent/status")
    async def pi_agent_status(request):
        status = discover_pi().to_dict()
        return web.json_response({"plugin_version": __version__, "pi": status, "models": inventory_models(50), "integrations": integration_status()})

    @routes.post("/pi-agent/workflow/analyze")
    async def pi_agent_analyze(request):
        payload = await request.json()
        workflow = payload.get("workflow", {})
        return web.json_response(analyze_workflow(workflow).to_dict())

    @routes.get("/pi-agent/integrations/minimax-h3-director/status")
    async def pi_agent_minimax_status(request):
        module = _minimax_h3()
        return web.json_response({
            "status": module.find_minimax_h3_director_install(),
            "profile": module.load_minimax_h3_director_profile(),
        })

    @routes.post("/pi-agent/integrations/minimax-h3-director/inspect")
    async def pi_agent_minimax_inspect(request):
        payload = await request.json()
        return web.json_response(_minimax_h3().inspect_minimax_h3_director_workflow(payload.get("workflow", {})))

    @routes.post("/pi-agent/integrations/minimax-h3-director/plan")
    async def pi_agent_minimax_plan(request):
        payload = await request.json()
        return web.json_response(_minimax_h3().create_minimax_h3_director_plan(
            request=payload.get("request", ""),
            mode=payload.get("mode", "auto"),
            duration_seconds=float(payload.get("duration_seconds", 5.0)),
            prompt_format=payload.get("prompt_format", "minimax"),
            reference_images=int(payload.get("reference_images", 0)),
            reference_videos=int(payload.get("reference_videos", 0)),
            reference_audios=int(payload.get("reference_audios", 0)),
            use_preview_override=bool(payload.get("use_preview_override", True)),
            use_enhance_prompt=bool(payload.get("use_enhance_prompt", False)),
            retake=bool(payload.get("retake", False)),
        ))

    @routes.post("/pi-agent/integrations/minimax-h3-director/workflow")
    async def pi_agent_minimax_workflow(request):
        payload = await request.json()
        result = _minimax_h3().create_minimax_h3_director_workflow(
            request=payload.get("request", ""),
            mode=payload.get("mode", "auto"),
            duration_seconds=float(payload.get("duration_seconds", 5.0)),
            prompt_format=payload.get("prompt_format", "minimax"),
            reference_images=int(payload.get("reference_images", 0)),
            reference_videos=int(payload.get("reference_videos", 0)),
            reference_audios=int(payload.get("reference_audios", 0)),
            use_preview_override=bool(payload.get("use_preview_override", True)),
            use_enhance_prompt=bool(payload.get("use_enhance_prompt", False)),
            retake=bool(payload.get("retake", False)),
        )
        return web.json_response(result, status=200 if result.get("ok") else 409)

    @routes.post("/pi-agent/integrations/context")
    async def pi_agent_integration_context(request):
        payload = await request.json()
        include_context = bool(payload.get("include_context", False))
        if include_context:
            return web.json_response(build_dynamic_integration_context(
                workflow=payload.get("workflow"),
                message=payload.get("message", ""),
            ))
        return web.json_response(integration_status(
            workflow=payload.get("workflow"),
            message=payload.get("message", ""),
        ))

    @routes.get("/pi-agent/integrations/whatdreamscost/status")
    async def pi_agent_wdc_status(request):
        module = _whatdreamscost()
        return web.json_response({
            "status": module.find_whatdreamscost_install(),
            "profile": module.load_whatdreamscost_profile(),
        })

    @routes.post("/pi-agent/integrations/whatdreamscost/inspect")
    async def pi_agent_wdc_inspect(request):
        payload = await request.json()
        return web.json_response(_whatdreamscost().inspect_whatdreamscost_workflow(payload.get("workflow", {})))

    @routes.post("/pi-agent/integrations/whatdreamscost/plan")
    async def pi_agent_wdc_plan(request):
        payload = await request.json()
        return web.json_response(_whatdreamscost().create_whatdreamscost_plan(
            request=payload.get("request", ""),
            workflow_mode=payload.get("workflow_mode", "director"),
            preferred_format=payload.get("preferred_format", "auto"),
            use_prompt_relay=bool(payload.get("use_prompt_relay", True)),
            use_custom_audio=bool(payload.get("use_custom_audio", False)),
            use_ic_lora=bool(payload.get("use_ic_lora", False)),
            retake=bool(payload.get("retake", False)),
        ))

    @routes.post("/pi-agent/integrations/whatdreamscost/workflow")
    async def pi_agent_wdc_workflow(request):
        payload = await request.json()
        result = _whatdreamscost().create_whatdreamscost_workflow(
            request=payload.get("request", ""),
            workflow_mode=payload.get("workflow_mode", "director"),
            preferred_format=payload.get("preferred_format", "auto"),
            use_prompt_relay=bool(payload.get("use_prompt_relay", True)),
            use_custom_audio=bool(payload.get("use_custom_audio", False)),
            use_ic_lora=bool(payload.get("use_ic_lora", False)),
            retake=bool(payload.get("retake", False)),
        )
        return web.json_response(result, status=200 if result.get("ok") else 409)


    @routes.get("/pi-agent/integrations/scene-camera-action/status")
    async def pi_agent_scene_camera_action_status(request):
        module = _scene_camera_action()
        return web.json_response({
            "status": module.find_scene_camera_action_install(),
            "profile": module.load_scene_camera_action_profile(),
        })

    @routes.post("/pi-agent/integrations/scene-camera-action/inspect")
    async def pi_agent_scene_camera_action_inspect(request):
        payload = await request.json()
        return web.json_response(_scene_camera_action().inspect_scene_camera_action_workflow(payload.get("workflow", {})))

    @routes.post("/pi-agent/integrations/scene-camera-action/plan")
    async def pi_agent_scene_camera_action_plan(request):
        payload = await request.json()
        return web.json_response(_scene_camera_action().create_scene_camera_action_plan(
            request=payload.get("request", ""),
            actor_type=payload.get("actor_type", "human"),
            duration_seconds=float(payload.get("duration_seconds", 7.0)),
            include_directing=bool(payload.get("include_directing", True)),
            scene_source=payload.get("scene_source", "generated"),
        ))

    @routes.post("/pi-agent/integrations/scene-camera-action/workflow")
    async def pi_agent_scene_camera_action_workflow(request):
        payload = await request.json()
        result = _scene_camera_action().create_scene_camera_action_workflow(
            request=payload.get("request", ""),
            actor_type=payload.get("actor_type", "human"),
            duration_seconds=float(payload.get("duration_seconds", 7.0)),
            include_directing=bool(payload.get("include_directing", True)),
            scene_source=payload.get("scene_source", "generated"),
        )
        return web.json_response(result, status=200 if result.get("ok") else 409)

    @routes.get("/pi-agent/integrations/minimax-h3-turbo/status")
    async def pi_agent_minimax_h3_turbo_status(request):
        module = _minimax_h3_turbo()
        return web.json_response({
            "status": module.find_minimax_h3_turbo_install(),
            "profile": module.load_minimax_h3_turbo_profile(),
        })

    @routes.post("/pi-agent/integrations/minimax-h3-turbo/inspect")
    async def pi_agent_minimax_h3_turbo_inspect(request):
        payload = await request.json()
        return web.json_response(_minimax_h3_turbo().inspect_minimax_h3_turbo_workflow(payload.get("workflow", {})))

    @routes.post("/pi-agent/integrations/minimax-h3-turbo/plan")
    async def pi_agent_minimax_h3_turbo_plan(request):
        payload = await request.json()
        return web.json_response(_minimax_h3_turbo().create_minimax_h3_turbo_plan(
            request=payload.get("request", ""),
            mode=payload.get("mode", "t2v"),
            steps=int(payload.get("steps", 4)),
            lora_strength=float(payload.get("lora_strength", 1.0)),
            low_vram=bool(payload.get("low_vram", False)),
        ))

    @routes.post("/pi-agent/integrations/minimax-h3-turbo/workflow")
    async def pi_agent_minimax_h3_turbo_workflow(request):
        payload = await request.json()
        result = _minimax_h3_turbo().create_minimax_h3_turbo_workflow(
            request=payload.get("request", ""),
            mode=payload.get("mode", "t2v"),
            steps=int(payload.get("steps", 4)),
            lora_strength=float(payload.get("lora_strength", 1.0)),
            low_vram=bool(payload.get("low_vram", False)),
        )
        return web.json_response(result, status=200 if result.get("ok") else 409)

    @routes.post("/pi-agent/tutorial/compile")
    async def pi_agent_tutorial_compile(request):
        payload = await request.json()
        result = compile_tutorial(payload.get("workflows", []), payload.get("title", "ComfyUI Project Tutorial"), payload.get("output_directory", ""), payload.get("detail_level", "complete"))
        return web.json_response({"tutorial_directory": result["tutorial_directory"], "controller_workflow": result["controller_workflow"], "overview_workflow": result["overview_workflow"]})

    @routes.get("/pi-agent/chat/sessions")
    async def pi_agent_chat_sessions(request):
        return web.json_response({"sessions": CHAT_MANAGER.store.list()})

    @routes.post("/pi-agent/chat/new")
    async def pi_agent_chat_new(request):
        payload = await request.json()
        session = CHAT_MANAGER.store.create(
            payload.get("title", "New chat"),
            payload.get("project_directory", ""),
            payload.get("provider", ""),
            payload.get("model", ""),
        )
        return web.json_response({"session": session})

    @routes.get(r"/pi-agent/chat/session/{session_id}")
    async def pi_agent_chat_get(request):
        try:
            session = CHAT_MANAGER.store.load(request.match_info["session_id"])
            return web.json_response({"session": session})
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)

    @routes.delete(r"/pi-agent/chat/session/{session_id}")
    async def pi_agent_chat_delete(request):
        deleted = CHAT_MANAGER.delete(request.match_info["session_id"])
        return web.json_response({"deleted": deleted})

    @routes.post("/pi-agent/chat/clear")
    async def pi_agent_chat_clear(request):
        payload = await request.json()
        try:
            session = CHAT_MANAGER.clear(str(payload.get("session_id", "")))
            return web.json_response({"session": session})
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)

    @routes.post("/pi-agent/chat/abort")
    async def pi_agent_chat_abort(request):
        payload = await request.json()
        return web.json_response({"aborted": CHAT_MANAGER.abort(str(payload.get("session_id", "")))})

    @routes.post("/pi-agent/chat/send")
    async def pi_agent_chat_send(request):
        payload = await request.json()
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            session = CHAT_MANAGER.store.create(
                "New chat",
                payload.get("project_directory", ""),
                payload.get("provider", ""),
                payload.get("model", ""),
            )
            session_id = session["session_id"]
        try:
            result = await asyncio.to_thread(
                CHAT_MANAGER.send,
                session_id,
                payload.get("message", ""),
                payload.get("project_directory", ""),
                payload.get("provider", ""),
                payload.get("model", ""),
                payload.get("pi_executable", ""),
                int(payload.get("timeout_seconds", 180)),
                payload.get("workflow"),
                payload.get("project_context", ""),
                bool(payload.get("preemptive_handoff", True)),
                payload.get("handoff_threshold_percent", 82.5),
                payload.get("handoff_max_chars", 8000),
            )
            return web.json_response(result, status=200 if result.get("ok") else 503)
        except ValueError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=404)

    _REGISTERED = True
    return True
