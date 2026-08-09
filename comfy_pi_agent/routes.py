from __future__ import annotations

import asyncio
import json
import uuid

from .chat import CHAT_MANAGER
from .models import inventory_models
from .pi_runtime import discover_pi
from .local_llm import discover_local_servers, local_provider_presets, probe_local_server, runtime_environment
from .provider_catalog import provider_options
from .terminal import TERMINAL_MANAGER
from .tutorials import compile_tutorial
from .version import __version__
from .workflow import analyze_workflow
from .workflow_guard import finalize_generated_workflow, finalize_workflow_result, live_node_catalog
from .workflow_screenshots import SCREENSHOT_BROKER, capture_with_playwright
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

    @routes.get("/pi-agent/workflow/capabilities")
    async def pi_agent_workflow_capabilities(request):
        return web.json_response(live_node_catalog())

    @routes.post("/pi-agent/workflow/finalize")
    async def pi_agent_workflow_finalize(request):
        payload = await request.json()
        minimum_gap = max(6.0, float(payload.get("minimum_node_gap_px", 6) or 6))
        result = finalize_generated_workflow(
            payload.get("workflow", {}),
            minimum_gap=minimum_gap,
            organize=bool(payload.get("organize", True)),
        )

        api_prompt = payload.get("api_prompt")
        if api_prompt is None and result.get("format") == "api":
            api_prompt = result.get("workflow")

        native = {
            "attempted": False,
            "valid": False,
            "reason": "No API prompt graph was supplied. UI static validation cannot substitute for native ComfyUI prompt validation.",
        }
        if isinstance(api_prompt, dict) and api_prompt:
            api_gate = finalize_generated_workflow(api_prompt, minimum_gap=minimum_gap, organize=False)
            if api_gate.get("valid"):
                try:
                    import execution  # type: ignore
                    valid = await execution.validate_prompt(str(uuid.uuid4()), api_gate["workflow"], None)
                    native = {
                        "attempted": True,
                        "valid": bool(valid[0]),
                        "error": valid[1],
                        "outputs_to_execute": valid[2],
                        "node_errors": valid[3],
                    }
                except Exception as exc:
                    native = {
                        "attempted": True,
                        "valid": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "outputs_to_execute": [],
                        "node_errors": {},
                    }
            else:
                native = {
                    "attempted": False,
                    "valid": False,
                    "reason": "API prompt failed the live static gate before native validation.",
                    "api_gate": {key: value for key, value in api_gate.items() if key != "workflow"},
                }

        result["native_validation"] = native
        result["completion_verified"] = bool(
            result.get("valid")
            and native.get("attempted")
            and native.get("valid")
            and native.get("outputs_to_execute")
        )
        return web.json_response(result, status=200 if result.get("valid") else 409)

    @routes.post("/pi-agent/screenshot/request")
    async def pi_agent_screenshot_request(request):
        payload = await request.json()
        try:
            timeout = max(5.0, min(60.0, float(payload.get("timeout_seconds", 35) or 35)))
            result = await SCREENSHOT_BROKER.request(payload, timeout=timeout)
        except ValueError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except asyncio.TimeoutError:
            return web.json_response({
                "ok": False,
                "error": (
                    "Timed out waiting for the active ComfyUI browser to capture the workflow. "
                    "Keep the ComfyUI page open and make sure this custom-node web extension is loaded."
                ),
            }, status=504)

        if not result.get("ok"):
            return web.json_response(result, status=409)

        metadata = result.get("metadata") or {}
        headers = {
            "X-ComfyUI-Pi-Width": str(metadata.get("width") or 0),
            "X-ComfyUI-Pi-Height": str(metadata.get("height") or 0),
            "X-ComfyUI-Pi-Mode": str(metadata.get("mode") or ""),
            "X-ComfyUI-Pi-Node-Id": str(metadata.get("node_id") or ""),
            "X-ComfyUI-Pi-Node-Type": str(metadata.get("node_type") or ""),
            "X-ComfyUI-Pi-Padding": str(metadata.get("padding_px") or 0),
            "X-ComfyUI-Pi-Node-Width": str(metadata.get("node_width_px") or 0),
            "X-ComfyUI-Pi-Node-Height": str(metadata.get("node_height_px") or 0),
            "X-ComfyUI-Pi-Capture-Backend": str(metadata.get("capture_backend") or ""),
        }
        return web.Response(body=result["png"], content_type="image/png", headers=headers)

    @routes.post("/pi-agent/screenshot/playwright")
    async def pi_agent_screenshot_playwright(request):
        payload = await request.json()
        base_url = f"{request.scheme}://{request.host}"
        try:
            result = await capture_with_playwright(payload, base_url=base_url)
        except ValueError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except RuntimeError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=503)
        except Exception as exc:
            return web.json_response(
                {"ok": False, "error": f"Playwright capture failed: {exc}"},
                status=500,
            )

        metadata = result.get("metadata") or {}
        headers = {
            "X-ComfyUI-Pi-Width": str(metadata.get("width") or 0),
            "X-ComfyUI-Pi-Height": str(metadata.get("height") or 0),
            "X-ComfyUI-Pi-Mode": str(metadata.get("mode") or ""),
            "X-ComfyUI-Pi-Node-Id": str(metadata.get("node_id") or ""),
            "X-ComfyUI-Pi-Node-Type": str(metadata.get("node_type") or ""),
            "X-ComfyUI-Pi-Padding": str(metadata.get("padding_px") or 0),
            "X-ComfyUI-Pi-Node-Width": str(metadata.get("node_width_px") or 0),
            "X-ComfyUI-Pi-Node-Height": str(metadata.get("node_height_px") or 0),
            "X-ComfyUI-Pi-Capture-Backend": str(metadata.get("capture_backend") or ""),
        }
        return web.Response(body=result["png"], content_type="image/png", headers=headers)

    @routes.get("/pi-agent/screenshot/pending")
    async def pi_agent_screenshot_pending(request):
        return web.json_response({"request": SCREENSHOT_BROKER.claim()})

    @routes.post(r"/pi-agent/screenshot/complete/{request_id}")
    async def pi_agent_screenshot_complete(request):
        request_id = request.match_info["request_id"]
        if request.content_type == "image/png":
            png = await request.read()
            metadata = {
                "width": request.query.get("width", "0"),
                "height": request.query.get("height", "0"),
                "mode": request.query.get("mode", ""),
                "node_id": request.query.get("node_id", ""),
                "node_type": request.query.get("node_type", ""),
                "padding_px": request.query.get("padding_px", "0"),
                "node_width_px": request.query.get("node_width_px", "0"),
                "node_height_px": request.query.get("node_height_px", "0"),
                "capture_backend": request.query.get("capture_backend", ""),
            }
            accepted = SCREENSHOT_BROKER.complete(request_id, png, metadata)
        else:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            accepted = SCREENSHOT_BROKER.fail(
                request_id,
                str(payload.get("error") or "The ComfyUI browser could not capture the requested screenshot."),
            )
        return web.json_response({"ok": bool(accepted)}, status=200 if accepted else 404)

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
        result = finalize_workflow_result(result)
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
        result = finalize_workflow_result(result)
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
        result = finalize_workflow_result(result)
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
        result = finalize_workflow_result(result)
        return web.json_response(result, status=200 if result.get("ok") else 409)

    @routes.post("/pi-agent/tutorial/compile")
    async def pi_agent_tutorial_compile(request):
        payload = await request.json()
        result = compile_tutorial(payload.get("workflows", []), payload.get("title", "ComfyUI Project Tutorial"), payload.get("output_directory", ""), payload.get("detail_level", "complete"))
        return web.json_response({"tutorial_directory": result["tutorial_directory"], "controller_workflow": result["controller_workflow"], "overview_workflow": result["overview_workflow"]})


    @routes.get("/pi-agent/terminal/capability")
    async def pi_agent_terminal_capability(request):
        return web.json_response(TERMINAL_MANAGER.capability())

    @routes.get(r"/pi-agent/terminal/status/{session_id}")
    async def pi_agent_terminal_status(request):
        return web.json_response(TERMINAL_MANAGER.status(request.match_info["session_id"]))

    @routes.post("/pi-agent/terminal/start")
    async def pi_agent_terminal_start(request):
        payload = await request.json()
        session_id = str(payload.get("session_id", "") or "").strip()
        if not session_id:
            return web.json_response({"ok": False, "error": "A chat session is required."}, status=400)
        try:
            context_settings = {
                "preemptive_handoff": bool(payload.get("preemptive_handoff", True)),
                "handoff_threshold": float(payload.get("handoff_threshold_percent", 82.5) or 82.5) / 100.0,
                "handoff_max_chars": int(payload.get("handoff_max_chars", 8000) or 8000),
                "project_context": payload.get("project_context", ""),
                "comfyui_base_url": f"{request.scheme}://{request.host}",
            }

            # Opening/collapsing ComfyUI panels is a browser-renderer lifecycle event,
            # not a request to prepare the model or restart Pi.  If this session already
            # owns a live PTY, return it immediately.  This must happen before llama.cpp
            # readiness probing because a running Pi process is already attached to its
            # configured provider/model and re-probing can take the full model timeout.
            existing = TERMINAL_MANAGER.get(session_id)
            if existing and existing.status().running:
                existing.update_workflow(payload.get("workflow"))
                existing.update_bridge_config(context_settings)
                existing.resize(
                    int(payload.get("cols", existing.cols) or existing.cols),
                    int(payload.get("rows", existing.rows) or existing.rows),
                )
                document = CHAT_MANAGER.store.load(session_id)
                return web.json_response({
                    "ok": True,
                    "reattached": True,
                    "terminal": existing.status().to_dict(),
                    "session": document,
                })

            local = payload.get("local_llm") if isinstance(payload.get("local_llm"), dict) else {}
            document = CHAT_MANAGER.store.update_config(
                session_id,
                payload.get("project_directory", ""),
                payload.get("provider", ""),
                payload.get("model", ""),
                scoped_models=payload.get("scoped_models", ""),
                local_llm=local,
                preemptive_handoff=bool(payload.get("preemptive_handoff", True)),
                handoff_threshold=payload.get("handoff_threshold_percent", 82.5),
                handoff_max_chars=payload.get("handoff_max_chars", 8000),
            )
            provider = str(document.get("provider") or "")
            model = str(document.get("model") or "")
            saved_local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
            if str(saved_local.get("kind") or "") == "llama.cpp" and provider and model:
                await asyncio.to_thread(
                    CHAT_MANAGER._ensure_llama_router_model,
                    str(saved_local.get("base_url") or ""),
                    model,
                    float(payload.get("timeout_seconds", 180) or 180),
                )
            session = await asyncio.to_thread(
                TERMINAL_MANAGER.start,
                session_id=session_id,
                executable=payload.get("pi_executable", ""),
                project_directory=payload.get("project_directory", ""),
                provider=provider,
                model=model,
                scoped_models=payload.get("scoped_models", ""),
                timeout=int(payload.get("timeout_seconds", 180) or 180),
                cols=int(payload.get("cols", 100) or 100),
                rows=int(payload.get("rows", 32) or 32),
                resume=bool(payload.get("resume", False)),
                env_overrides=runtime_environment(saved_local),
                workflow=payload.get("workflow"),
                context_settings=context_settings,
            )
            return web.json_response({"ok": True, "terminal": session.status().to_dict(), "session": document})
        except (ValueError, FileNotFoundError, RuntimeError, TimeoutError, OSError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=503)

    @routes.post("/pi-agent/terminal/restart")
    async def pi_agent_terminal_restart(request):
        payload = await request.json()
        session_id = str(payload.get("session_id", "") or "").strip()
        if not session_id:
            return web.json_response({"ok": False, "error": "A chat session is required."}, status=400)
        try:
            document = CHAT_MANAGER.store.load(session_id)
            local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
            provider = str(payload.get("provider", document.get("provider", "")) or "")
            model = str(payload.get("model", document.get("model", "")) or "")
            if str(local.get("kind") or "") == "llama.cpp" and provider and model:
                await asyncio.to_thread(
                    CHAT_MANAGER._ensure_llama_router_model,
                    str(local.get("base_url") or ""),
                    model,
                    float(payload.get("timeout_seconds", 180) or 180),
                )
            session = await asyncio.to_thread(
                TERMINAL_MANAGER.restart,
                session_id=session_id,
                provider=provider,
                model=model,
                scoped_models=str(payload.get("scoped_models", document.get("scoped_models", "")) or ""),
                timeout=int(payload.get("timeout_seconds", 180) or 180),
                env_overrides=runtime_environment(local),
                workflow=payload.get("workflow"),
                context_settings={
                    "preemptive_handoff": bool(payload.get("preemptive_handoff", True)),
                    "handoff_threshold": float(payload.get("handoff_threshold_percent", 82.5) or 82.5) / 100.0,
                    "handoff_max_chars": int(payload.get("handoff_max_chars", 8000) or 8000),
                    "project_context": payload.get("project_context", ""),
                    "comfyui_base_url": f"{request.scheme}://{request.host}",
                },
            )
            document["provider"] = provider
            document["model"] = model
            CHAT_MANAGER.store.save(document)
            return web.json_response({"ok": True, "terminal": session.status().to_dict()})
        except (ValueError, FileNotFoundError, RuntimeError, TimeoutError, OSError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=503)

    @routes.post("/pi-agent/terminal/stop")
    async def pi_agent_terminal_stop(request):
        payload = await request.json()
        return web.json_response({"stopped": await asyncio.to_thread(TERMINAL_MANAGER.stop, str(payload.get("session_id", "")))})

    @routes.get(r"/pi-agent/terminal/ws/{session_id}")
    async def pi_agent_terminal_ws(request):
        session_id = request.match_info["session_id"]
        session = TERMINAL_MANAGER.get(session_id)
        if not session:
            return web.json_response({"error": "Pi terminal is not running for this session."}, status=404)
        ws = web.WebSocketResponse(heartbeat=20.0, autoping=True, max_msg_size=2 * 1024 * 1024)
        await ws.prepare(request)
        snapshot = session.attach_snapshot()
        if snapshot:
            await ws.send_str(json.dumps({"type": "output", "data": snapshot.decode("utf-8", errors="replace")}))

        async def pump_output():
            while not ws.closed:
                chunk = await asyncio.to_thread(session.read_output, 0.25)
                if chunk:
                    await ws.send_str(json.dumps({"type": "output", "data": chunk.decode("utf-8", errors="replace")}))
                status = session.status()
                if not status.running and status.recovering:
                    # Keep the browser attached while this same PiTerminalSession object
                    # reopens the persisted Pi session.
                    continue
                if not status.running:
                    await ws.send_str(json.dumps({"type": "exit", "status": status.to_dict()}))
                    break

        pump = asyncio.create_task(pump_output())
        try:
            async for message in ws:
                if message.type != web.WSMsgType.TEXT:
                    continue
                try:
                    payload = json.loads(message.data)
                except Exception:
                    payload = {"type": "input", "data": str(message.data)}
                kind = str(payload.get("type") or "input")
                if kind == "input":
                    session.write(str(payload.get("data") or ""))
                elif kind == "resize":
                    session.resize(int(payload.get("cols", session.cols)), int(payload.get("rows", session.rows)))
                elif kind == "workflow":
                    session.update_workflow(payload.get("workflow"))
                elif kind == "ping":
                    await ws.send_str(json.dumps({"type": "pong"}))
        finally:
            pump.cancel()
            try:
                await pump
            except BaseException:
                pass
        return ws

    @routes.get("/pi-agent/chat/sessions")
    async def pi_agent_chat_sessions(request):
        return web.json_response({"sessions": CHAT_MANAGER.store.list()})

    @routes.get("/pi-agent/chat/commands")
    async def pi_agent_chat_commands(request):
        session_id = str(request.query.get("session_id", "") or "")
        return web.json_response({"commands": CHAT_MANAGER.command_catalog(session_id)})

    @routes.get("/pi-agent/local-llm/presets")
    async def pi_agent_local_llm_presets(request):
        # Metadata only. This route never probes a server.
        return web.json_response({"providers": local_provider_presets()})

    @routes.get("/pi-agent/model/providers")
    async def pi_agent_model_providers(request):
        # Provider metadata only. This reads Pi's local models.json provider ids but
        # never starts Pi and never probes local inference servers.
        return web.json_response({"providers": provider_options()})

    @routes.get("/pi-agent/chat/model-catalog")
    async def pi_agent_chat_model_catalog(request):
        session_id = str(request.query.get("session_id", "") or "")
        executable = str(request.query.get("pi_executable", "") or "")
        project_directory = str(request.query.get("project_directory", "") or "")
        try:
            result = await asyncio.to_thread(
                CHAT_MANAGER.model_catalog,
                session_id,
                executable,
                project_directory,
                30,
            )
            return web.json_response(result)
        except (ValueError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/pi-agent/chat/model/select")
    async def pi_agent_chat_model_select(request):
        payload = await request.json()
        session_id = str(payload.get("session_id", "") or "").strip()
        if not session_id:
            return web.json_response({"ok": False, "error": "A chat session is required."}, status=400)
        try:
            result, document = await asyncio.to_thread(
                CHAT_MANAGER.select_model,
                session_id,
                payload.get("provider", ""),
                payload.get("model", ""),
                float(payload.get("timeout", 180) or 180),
            )
            result["session"] = document
            return web.json_response(result)
        except (ValueError, FileNotFoundError, RuntimeError, TimeoutError, OSError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.get("/pi-agent/local-llm/discover")
    async def pi_agent_local_llm_discover(request):
        # Explicit route call only: no server probing happens at plugin import/startup.
        results = await asyncio.to_thread(discover_local_servers)
        return web.json_response({"servers": results})

    @routes.post("/pi-agent/local-llm/probe")
    async def pi_agent_local_llm_probe(request):
        payload = await request.json()
        result = await asyncio.to_thread(
            probe_local_server,
            payload.get("kind", "openai-compatible"),
            payload.get("base_url", ""),
            float(payload.get("timeout", 2.5) or 2.5),
            bool(payload.get("reload_catalog", False)),
        )
        return web.json_response(result, status=200 if result.get("available") else 404)

    @routes.post("/pi-agent/local-llm/configure")
    async def pi_agent_local_llm_configure(request):
        payload = await request.json()
        try:
            session_id = str(payload.get("session_id", "") or "").strip()
            if not session_id:
                return web.json_response({"ok": False, "error": "A chat session is required."}, status=400)
            result, document = await asyncio.to_thread(
                CHAT_MANAGER.activate_local_provider,
                session_id,
                payload.get("kind", "openai-compatible"),
                payload.get("base_url", ""),
                payload.get("model", ""),
                payload.get("models") if isinstance(payload.get("models"), list) else [],
                payload.get("provider_id", ""),
                payload.get("api_key_env", ""),
                bool(payload.get("reload_catalog", False)),
            )
            result["session"] = document
            return web.json_response(result)
        except (ValueError, FileNotFoundError, RuntimeError, TimeoutError, OSError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.post("/pi-agent/chat/new")
    async def pi_agent_chat_new(request):
        payload = await request.json()
        session = CHAT_MANAGER.store.create(
            payload.get("title", "New chat"),
            payload.get("project_directory", ""),
            payload.get("provider", ""),
            payload.get("model", ""),
        )
        session["scoped_models"] = str(payload.get("scoped_models", "") or "")
        local = payload.get("local_llm") if isinstance(payload.get("local_llm"), dict) else {}
        session["local_llm"] = {k: v for k, v in local.items() if k not in {"api_key", "token", "secret"}} if local.get("enabled") else {}
        session = CHAT_MANAGER.store.save(session)
        return web.json_response({"session": session})

    @routes.post("/pi-agent/chat/import")
    async def pi_agent_chat_import(request):
        payload = await request.json()
        source = payload.get("session") if isinstance(payload.get("session"), dict) else payload
        try:
            session = CHAT_MANAGER.store.import_document(source)
            return web.json_response({"session": session})
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get(r"/pi-agent/chat/session/{session_id}")
    async def pi_agent_chat_get(request):
        try:
            session = CHAT_MANAGER.store.load(request.match_info["session_id"])
            return web.json_response({"session": session})
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)

    @routes.post(r"/pi-agent/chat/session/{session_id}/rename")
    async def pi_agent_chat_rename(request):
        payload = await request.json()
        try:
            session = CHAT_MANAGER.store.rename(
                request.match_info["session_id"],
                str(payload.get("title") or ""),
            )
            return web.json_response({"session": session})
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

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
                session_id=session_id,
                message=payload.get("message", ""),
                project_directory=payload.get("project_directory", ""),
                provider=payload.get("provider", ""),
                model=payload.get("model", ""),
                scoped_models=payload.get("scoped_models", ""),
                local_llm=payload.get("local_llm") if isinstance(payload.get("local_llm"), dict) else {},
                executable=payload.get("pi_executable", ""),
                timeout=int(payload.get("timeout_seconds", 180)),
                workflow=payload.get("workflow"),
                project_context=payload.get("project_context", ""),
                preemptive_handoff=bool(payload.get("preemptive_handoff", True)),
                handoff_threshold=payload.get("handoff_threshold_percent", 82.5),
                handoff_max_chars=payload.get("handoff_max_chars", 8000),
            )
            return web.json_response(result, status=200 if result.get("ok") else 503)
        except ValueError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=404)

    _REGISTERED = True
    return True
