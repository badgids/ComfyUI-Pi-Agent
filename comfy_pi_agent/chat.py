from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compat import get_comfy_user_directory
from .io_utils import atomic_write_json
from .pi_runtime import PiRpcClient, discover_pi
from .local_llm import runtime_environment
from .pi_commands import COMMAND_BY_NAME, command_catalog, command_help, parse_slash_command
from .provider_catalog import provider_options, simplified_models
from .integrations.router import build_dynamic_integration_context
from .workflow import analyze_workflow
from .agent_guidance import build_request_guidance, guidance_signature
from .context_handoff import (
    ContextPressure,
    DEFAULT_HANDOFF_MAX_CHARS,
    DEFAULT_HANDOFF_THRESHOLD,
    clamp_handoff_chars,
    clamp_threshold,
    context_pressure,
    create_handoff,
    handoff_bootstrap_prompt,
)
from .local_llm import (
    configure_local_provider,
    llama_router_action,
    llama_router_models,
    local_provider_id,
    probe_local_server,
)




def _is_url_like(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("http://") or text.startswith("https://")


def _normalized_provider_model(
    provider: str,
    model: str,
    local_llm: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Keep endpoint URLs out of Pi's provider field and repair old v0.1.9 sessions."""
    provider_value = str(provider or "").strip()
    model_value = str(model or "").strip()
    local = local_llm if isinstance(local_llm, dict) else {}
    if _is_url_like(provider_value):
        kind = str(local.get("kind") or "").strip()
        provider_value = local_provider_id(kind) if kind else ""
        if not model_value:
            model_value = str(local.get("model") or "").strip()
    return provider_value, model_value

def _now() -> float:
    return time.time()


def _safe_title(value: str, fallback: str = "New chat") -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return fallback
    return text[:80]


def _session_root() -> Path:
    root = get_comfy_user_directory() / "pi-agent" / "chat-sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_session_id(session_id: str) -> str:
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("Invalid chat session id.")
    return safe


def _session_path(session_id: str) -> Path:
    return _session_root() / f"{_safe_session_id(session_id)}.json"


def _workflow_context_path(session_id: str) -> Path:
    root = _session_root() / "context"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{_safe_session_id(session_id)}-active-workflow.json"


def _compact_workflow_summary(workflow: Any) -> str:
    """Return a bounded workflow digest suitable for normal chat context.

    The complete active workflow is saved separately and can be read by Pi on demand.
    This summary lets Pi decide whether that expensive read is actually necessary.
    """
    try:
        report = analyze_workflow(workflow).to_dict()
    except Exception as exc:
        return json.dumps({"summary_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
    compact_integrations: dict[str, Any] = {}
    for key, value in (report.get("integrations") or {}).items():
        if not isinstance(value, dict):
            continue
        compact_integrations[str(key)] = {
            "detected": value.get("detected"),
            "issues": (value.get("issues") or [])[:12],
            "warnings": (value.get("warnings") or [])[:12],
            "details": value.get("details") or {},
        }
    compact = {
        "format": report.get("format"),
        "node_count": report.get("node_count"),
        "link_count": report.get("link_count"),
        "node_types": report.get("node_types") or {},
        "missing_node_types": (report.get("missing_node_types") or [])[:50],
        "input_files": (report.get("input_files") or [])[:50],
        "model_candidates": (report.get("model_candidates") or [])[:50],
        "issues": (report.get("issues") or [])[:30],
        "integrations": compact_integrations,
    }
    return json.dumps(compact, ensure_ascii=False, indent=2)[:20_000]


def _new_document(
    title: str = "New chat",
    project_directory: str = "",
    provider: str = "",
    model: str = "",
) -> dict[str, Any]:
    timestamp = _now()
    return {
        "schema_version": 1,
        "session_id": uuid.uuid4().hex,
        "title": _safe_title(title),
        "created_at": timestamp,
        "updated_at": timestamp,
        "project_directory": str(project_directory or ""),
        "provider": str(provider or ""),
        "model": str(model or ""),
        "scoped_models": "",
        "local_llm": {},
        "messages": [],
        "context_guard": {
            "enabled": True,
            "threshold": DEFAULT_HANDOFF_THRESHOLD,
            "handoff_max_chars": DEFAULT_HANDOFF_MAX_CHARS,
            "handoff_count": 0,
            "last_pressure": {},
            "last_handoff": {},
        },
    }


class ChatSessionStore:
    """Small JSON-backed chat history store under ComfyUI user data."""

    def create(
        self,
        title: str = "New chat",
        project_directory: str = "",
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        document = _new_document(title, project_directory, provider, model)
        self.save(document)
        return document

    def save(self, document: dict[str, Any]) -> dict[str, Any]:
        document = dict(document)
        document["updated_at"] = _now()
        atomic_write_json(_session_path(str(document["session_id"])), document)
        return document

    def load(self, session_id: str) -> dict[str, Any]:
        path = _session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Chat session not found: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Chat session file is invalid.")
        data.setdefault("messages", [])
        data.setdefault("scoped_models", "")
        data.setdefault("local_llm", {})
        repaired_provider, repaired_model = _normalized_provider_model(
            str(data.get("provider") or ""),
            str(data.get("model") or ""),
            data.get("local_llm") if isinstance(data.get("local_llm"), dict) else {},
        )
        data["provider"] = repaired_provider
        data["model"] = repaired_model
        data.setdefault("context_guard", {
            "enabled": True,
            "threshold": DEFAULT_HANDOFF_THRESHOLD,
            "handoff_max_chars": DEFAULT_HANDOFF_MAX_CHARS,
            "handoff_count": 0,
            "last_pressure": {},
            "last_handoff": {},
        })
        return data

    def delete(self, session_id: str) -> bool:
        path = _session_path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def clear(self, session_id: str) -> dict[str, Any]:
        document = self.load(session_id)
        document["messages"] = []
        document["title"] = "New chat"
        return self.save(document)

    def append(self, session_id: str, role: str, content: str, **extra: Any) -> dict[str, Any]:
        document = self.load(session_id)
        message = {
            "id": uuid.uuid4().hex,
            "role": role,
            "content": str(content or ""),
            "created_at": _now(),
        }
        message.update(extra)
        document.setdefault("messages", []).append(message)
        if role == "user" and document.get("title") in {"", "New chat"}:
            document["title"] = _safe_title(content)
        return self.save(document)

    def update_config(
        self,
        session_id: str,
        project_directory: str = "",
        provider: str = "",
        model: str = "",
        scoped_models: str = "",
        local_llm: dict[str, Any] | None = None,
        preemptive_handoff: bool = True,
        handoff_threshold: float | int | str = DEFAULT_HANDOFF_THRESHOLD,
        handoff_max_chars: int | str = DEFAULT_HANDOFF_MAX_CHARS,
    ) -> dict[str, Any]:
        document = self.load(session_id)
        document["project_directory"] = str(project_directory or "")
        provider_value, model_value = _normalized_provider_model(provider, model, local_llm)
        document["provider"] = provider_value
        document["model"] = model_value
        document["scoped_models"] = str(scoped_models or "")
        if isinstance(local_llm, dict):
            # Never persist a raw API key in chat JSON. Local servers normally need no key;
            # authenticated OpenAI-compatible endpoints should use an environment variable.
            clean_local = {k: v for k, v in local_llm.items() if k not in {"api_key", "token", "secret"}}
            document["local_llm"] = clean_local if clean_local.get("enabled") else {}
        guard = document.setdefault("context_guard", {})
        guard["enabled"] = bool(preemptive_handoff)
        guard["threshold"] = clamp_threshold(handoff_threshold)
        guard["handoff_max_chars"] = clamp_handoff_chars(handoff_max_chars)
        guard.setdefault("handoff_count", 0)
        guard.setdefault("last_pressure", {})
        guard.setdefault("last_handoff", {})
        return self.save(document)

    def update_context_guard(
        self,
        session_id: str,
        pressure: dict[str, Any],
        handoff: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document = self.load(session_id)
        guard = document.setdefault("context_guard", {})
        guard["last_pressure"] = pressure
        if handoff:
            guard["handoff_count"] = int(guard.get("handoff_count", 0) or 0) + 1
            guard["last_handoff"] = handoff
        return self.save(document)

    def list(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in sorted(_session_root().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            messages = data.get("messages", []) if isinstance(data, dict) else []
            result.append({
                "session_id": data.get("session_id", path.stem),
                "title": data.get("title", "Chat"),
                "updated_at": data.get("updated_at", path.stat().st_mtime),
                "message_count": len(messages) if isinstance(messages, list) else 0,
                "project_directory": data.get("project_directory", ""),
                "provider": data.get("provider", ""),
                "model": data.get("model", ""),
                "scoped_models": data.get("scoped_models", ""),
                "local_llm": data.get("local_llm", {}),
                "context_guard": data.get("context_guard", {}),
            })
        return result


@dataclass
class _LiveSession:
    client: PiRpcClient
    project_directory: str
    provider: str
    model: str
    executable: str
    lock: threading.Lock
    scoped_models: str = ""
    local_signature: str = ""
    context_signature: str | None = None
    handoff_ingested: bool = False


class ChatRuntimeManager:
    """Keeps one Pi RPC process per active sidebar conversation."""

    def __init__(self) -> None:
        self.store = ChatSessionStore()
        self._live: dict[str, _LiveSession] = {}
        self._guard = threading.RLock()

    def _close_live(self, session_id: str) -> None:
        with self._guard:
            live = self._live.pop(session_id, None)
        if live:
            live.client.close()

    def close(self, session_id: str) -> None:
        self._close_live(session_id)

    @staticmethod
    def _ensure_llama_router_model(base_url: str, model: str) -> dict[str, Any]:
        """Best-effort router load so model switching also works with autoload disabled."""
        model_id = str(model or "").strip()
        if not model_id:
            return {"attempted": False, "status": "no-model"}
        try:
            catalog = llama_router_models(base_url, timeout=2.0)
        except Exception:
            # Single-model llama-server does not need the router management API.
            return {"attempted": False, "status": "single-model-or-router-unavailable"}
        entry = next((item for item in catalog.get("models", []) if str(item.get("id") or "") == model_id), None)
        if not entry:
            return {"attempted": False, "status": "not-in-router-catalog"}
        status = str(entry.get("status") or "unknown")
        if status in {"loaded", "loading", "sleeping"}:
            return {"attempted": False, "status": status}
        if status != "unloaded" or bool(entry.get("failed", False)):
            return {"attempted": False, "status": status}
        try:
            result = llama_router_action("load", model_id, base_url, timeout=20.0)
            return {"attempted": True, "status": "load-requested", "result": result}
        except Exception as exc:
            # The normal router default is autoload-on-request, so a management-route
            # failure should not block selecting the model in Pi.
            return {"attempted": True, "status": "load-request-failed", "error": f"{type(exc).__name__}: {exc}"}

    def activate_local_provider(
        self,
        session_id: str,
        kind: str,
        base_url: str = "",
        model: str = "",
        models: list[str] | None = None,
        provider_id: str = "",
        api_key_env: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Probe/configure a local provider and make it the chat's active model source.

        The currently running Pi RPC process is closed because its available-model snapshot
        is immutable until Pi reloads/restarts. The next message starts Pi with the freshly
        written models.json provider and selected model.
        """
        result = configure_local_provider(
            kind, base_url, models=models, model=model, provider_id=provider_id, api_key_env=api_key_env
        )
        document = self.store.load(session_id)
        if str(result.get("kind") or "") == "llama.cpp" and str(result.get("model") or ""):
            result["router_load"] = self._ensure_llama_router_model(
                str(result.get("base_url") or ""), str(result.get("model") or "")
            )
        document["provider"] = str(result.get("provider") or "")
        document["model"] = str(result.get("model") or "")
        document["local_llm"] = {
            "enabled": True,
            "kind": str(result.get("kind") or ""),
            "base_url": str(result.get("base_url") or ""),
            "provider": str(result.get("provider") or ""),
            "model": str(result.get("model") or ""),
            "models": list(result.get("models") or []),
            "api_key_env": str(result.get("api_key_env") or ""),
        }
        document = self.store.save(document)
        self._close_live(session_id)
        return result, document

    def delete(self, session_id: str) -> bool:
        self._close_live(session_id)
        try:
            _workflow_context_path(session_id).unlink(missing_ok=True)
        except Exception:
            pass
        return self.store.delete(session_id)

    def clear(self, session_id: str) -> dict[str, Any]:
        self._close_live(session_id)
        try:
            _workflow_context_path(session_id).unlink(missing_ok=True)
        except Exception:
            pass
        return self.store.clear(session_id)

    def abort(self, session_id: str) -> bool:
        with self._guard:
            live = self._live.get(session_id)
        if not live:
            return False
        try:
            live.client.send({"type": "abort"})
            return True
        except Exception:
            return False

    @staticmethod
    def _model_label(model: dict[str, Any]) -> tuple[str, str]:
        provider = str(model.get("provider") or model.get("providerId") or "").strip()
        model_id = str(model.get("id") or model.get("modelId") or model.get("name") or "").strip()
        return provider, model_id

    def command_catalog(self, session_id: str = "") -> list[dict[str, Any]]:
        """Return Pi built-ins plus any RPC-discoverable extension/template/skill commands."""
        commands = command_catalog()
        seen = {str(item.get("name") or "") for item in commands}
        live = None
        if session_id:
            with self._guard:
                live = self._live.get(session_id)
        if live:
            try:
                for item in live.client.get_commands():
                    name = str(item.get("name") or "").strip()
                    if not name or name in seen:
                        continue
                    commands.append({
                        "name": name,
                        "description": str(item.get("description") or f"Pi {item.get('source', 'dynamic')} command"),
                        "usage": f"/{name}",
                        "mode": "pi",
                        "source": item.get("source", "pi"),
                    })
                    seen.add(name)
            except Exception:
                pass
        return commands

    def model_catalog(
        self,
        session_id: str = "",
        executable: str = "",
        project_directory: str = "",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Return Pi provider metadata plus the models Pi can actually use.

        Provider metadata is always available without probing local inference servers. The
        model list comes from Pi's own get_available_models RPC snapshot. When this chat
        already has a live Pi process we reuse it; otherwise a short-lived lean RPC process
        is created and closed immediately. Local hosts are still probed only when the user
        explicitly selects/refreshes that local provider.
        """
        document: dict[str, Any] = {}
        if session_id:
            try:
                document = self.store.load(session_id)
            except FileNotFoundError:
                document = {}
        cwd = str(project_directory or document.get("project_directory") or "")
        models: list[dict[str, Any]] = []
        state: dict[str, Any] = {}
        runtime_error = ""

        live = None
        if session_id:
            with self._guard:
                live = self._live.get(session_id)
        if live:
            try:
                with live.lock:
                    models = live.client.get_available_models()
                    state = live.client.get_state()
            except Exception as exc:
                runtime_error = f"{type(exc).__name__}: {exc}"
        else:
            status = discover_pi(executable)
            if not status.available or not status.executable:
                runtime_error = status.message
            else:
                client = None
                try:
                    client = PiRpcClient(
                        str(status.executable),
                        project_dir=cwd,
                        timeout=max(10, min(int(timeout or 30), 60)),
                    )
                    models = client.get_available_models()
                    state = client.get_state()
                except Exception as exc:
                    runtime_error = f"{type(exc).__name__}: {exc}"
                finally:
                    if client is not None:
                        client.close()

        safe_models = simplified_models(models)
        current_provider = str(document.get("provider") or "").strip()
        current_model = str(document.get("model") or "").strip()
        if not current_provider or not current_model:
            state_provider, state_model = self._model_label(state.get("model") if isinstance(state, dict) else {})
            current_provider = current_provider or state_provider
            current_model = current_model or state_model
        return {
            "providers": provider_options(models),
            "models": safe_models,
            "current": {"provider": current_provider, "model": current_model},
            "runtime_error": runtime_error,
        }

    def select_model(self, session_id: str, provider: str = "", model: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
        """Persist a provider/model selection and switch the live Pi process when possible."""
        document = self.store.load(session_id)
        provider_value = str(provider or "").strip()
        model_value = str(model or "").strip()
        if _is_url_like(provider_value):
            raise ValueError("A provider id cannot be an endpoint URL.")

        # Pi default means no explicit provider/model flags. A fresh lean RPC process is
        # required because RPC has no 'restore startup default' command. Visible chat history
        # remains in ComfyUI-Pi and is rehydrated on the next turn.
        if not provider_value and not model_value:
            document["provider"] = ""
            document["model"] = ""
            document["local_llm"] = {}
            document = self.store.save(document)
            self._close_live(session_id)
            return {"ok": True, "provider": "", "model": "", "switched_live": False}, document
        if not provider_value or not model_value:
            raise ValueError("Both provider and model are required when selecting an explicit Pi model.")

        selected: dict[str, Any] = {}
        switched_live = False
        local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
        if (
            str(local.get("kind") or "") == "llama.cpp"
            and str(local.get("provider") or "") == provider_value
        ):
            self._ensure_llama_router_model(str(local.get("base_url") or ""), model_value)

        with self._guard:
            live = self._live.get(session_id)
        if live:
            with live.lock:
                selected = live.client.set_model(provider_value, model_value)
            selected_provider, selected_model = self._model_label(selected)
            provider_value = selected_provider or provider_value
            model_value = selected_model or model_value
            live.provider = provider_value
            live.model = model_value
            switched_live = True

        document["provider"] = provider_value
        document["model"] = model_value
        local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
        if local and str(local.get("provider") or "") != provider_value:
            document["local_llm"] = {}
        elif local:
            local = dict(local)
            local["model"] = model_value
            document["local_llm"] = local
        document = self.store.save(document)
        return {
            "ok": True,
            "provider": provider_value,
            "model": model_value,
            "switched_live": switched_live,
            "selected": simplified_models([selected])[0] if selected else {},
        }, document

    @staticmethod
    def _format_models(models: list[dict[str, Any]], current: dict[str, Any] | None = None, limit: int = 120) -> str:
        current_provider, current_id = ChatRuntimeManager._model_label(current or {})
        lines = ["Available Pi models:"]
        for item in models[:limit]:
            provider, model_id = ChatRuntimeManager._model_label(item)
            if not model_id:
                continue
            label = f"{provider}/{model_id}" if provider else model_id
            marker = " ← current" if provider == current_provider and model_id == current_id else ""
            lines.append(f"- `{label}`{marker}")
        if len(models) > limit:
            lines.append(f"- … {len(models) - limit} more models omitted from this view")
        lines.append("\nSwitch with `/model provider/model-id`.")
        return "\n".join(lines)

    @staticmethod
    def _format_tree(tree: Any, max_chars: int = 12_000) -> str:
        try:
            text = json.dumps(tree, ensure_ascii=False, indent=2)
        except Exception:
            text = str(tree)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n… tree output truncated"
        return "Pi session tree:\n```json\n" + text + "\n```"

    def _move_live_session(self, old_id: str, new_id: str, live: _LiveSession) -> None:
        with self._guard:
            if self._live.get(old_id) is live:
                self._live.pop(old_id, None)
            self._live[new_id] = live

    def _duplicate_visible_session(self, document: dict[str, Any], title: str) -> dict[str, Any]:
        clone = _new_document(
            title=title,
            project_directory=str(document.get("project_directory") or ""),
            provider=str(document.get("provider") or ""),
            model=str(document.get("model") or ""),
        )
        clone["messages"] = [dict(item) for item in (document.get("messages") or []) if isinstance(item, dict)]
        clone["scoped_models"] = str(document.get("scoped_models") or "")
        clone["local_llm"] = dict(document.get("local_llm") or {}) if isinstance(document.get("local_llm"), dict) else {}
        clone["context_guard"] = dict(document.get("context_guard") or {})
        return self.store.save(clone)

    def _manual_handoff(
        self,
        session_id: str,
        live: _LiveSession,
        document: dict[str, Any],
        project_context: str,
        workflow_summary: str,
        workflow_path: str,
        routed: dict[str, Any],
        threshold: float,
        max_chars: int,
        focus: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            stats = live.client.get_session_stats()
        except Exception:
            stats = {}
        usage = stats.get("contextUsage") if isinstance(stats, dict) else {}
        tokens = int((usage or {}).get("tokens") or 0) if isinstance(usage, dict) else 0
        window = int((usage or {}).get("contextWindow") or 0) if isinstance(usage, dict) else 0
        ratio = (tokens / window) if tokens and window else 0.0
        pressure = ContextPressure(tokens, window, ratio, threshold, True, source="manual_slash_command")
        manual_context = project_context
        if focus.strip():
            manual_context = (manual_context + "\n\nManual /compact focus: " + focus.strip()).strip()
        summarizer = self._handoff_summarizer(
            live.executable,
            live.project_directory,
            live.provider,
            live.model,
            live.scoped_models,
            document.get("local_llm", {}),
            live.client.timeout,
        )
        handoff = create_handoff(
            session_id=session_id,
            document=document,
            pressure=pressure,
            project_context=manual_context,
            workflow_summary=workflow_summary,
            workflow_context_path=workflow_path,
            routed_context=routed,
            max_chars=max_chars,
            summarizer=summarizer,
        )
        live.client.new_session()
        handoff_text = Path(str(handoff["path"])).read_text(encoding="utf-8")
        bootstrap = live.client.prompt(handoff_bootstrap_prompt(str(handoff["path"]), handoff_text=handoff_text))
        post_pressure = self._pressure_from_prompt_result(bootstrap, threshold).to_dict()
        handoff = dict(handoff)
        handoff.update({
            "ingested": True,
            "bootstrap_acknowledged": str(bootstrap.get("text") or "").strip().upper() == "HANDOFF_READY",
            "reset_method": "new_session",
            "trigger_pressure": pressure.to_dict(),
            "post_reset_pressure": post_pressure,
            "manual": True,
        })
        document = self.store.update_context_guard(session_id, post_pressure, handoff=handoff)
        live.context_signature = None
        live.handoff_ingested = True
        return document, handoff

    def _handle_builtin_command(
        self,
        session_id: str,
        text: str,
        parsed: tuple[str, list[str], str],
        document: dict[str, Any],
        live: _LiveSession,
        project_context: str,
        workflow_summary: str,
        workflow_path: str,
        workflow: Any,
        threshold: float,
        max_handoff_chars: int,
        executable: str,
    ) -> dict[str, Any] | None:
        name, args, raw_args = parsed
        if name not in COMMAND_BY_NAME:
            return None

        ui_action = ""
        switch_session_id = ""
        handoff: dict[str, Any] | None = None
        response_text = ""

        if name == "hotkeys":
            response_text = (
                "ComfyUI-Pi chat shortcuts:\n"
                "- Enter — send\n- Shift+Enter — new line\n- Escape/Stop — abort active Pi work\n"
                "- Ctrl/Cmd+C — copy selected chat text\n- Ctrl/Cmd+V — paste text\n\n" + command_help()
            )
        elif name == "model":
            state = live.client.get_state()
            if not args:
                response_text = self._format_models(live.client.get_available_models(), state.get("model") if isinstance(state, dict) else {})
            elif args[0].lower() in {"next", "+"}:
                changed = live.client.cycle_model() or {}
                selected = changed.get("model") if isinstance(changed, dict) else {}
                provider, model_id = self._model_label(selected if isinstance(selected, dict) else {})
                response_text = f"Switched Pi model to `{provider}/{model_id}`." if model_id else "Pi has no additional model to cycle to."
            else:
                local_aliases = {
                    "llama.cpp", "llamacpp", "llama-cpp", "llama_cpp",
                    "ollama", "lm-studio", "lmstudio", "lm_studio", "vllm",
                    "openai-compatible", "openai", "generic",
                }
                first = args[0]
                # Dead-simple local-provider form: `/model llama.cpp` means "use llama.cpp",
                # not "find a model literally named llama.cpp under the current provider".
                if len(args) == 1 and first.lower() in local_aliases:
                    current_local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
                    requested_provider = local_provider_id(first)
                    base_url = str(current_local.get("base_url") or "") if str(current_local.get("provider") or "") == requested_provider else ""
                    preferred = str(current_local.get("model") or "") if str(current_local.get("provider") or "") == requested_provider else ""
                    configured, document = self.activate_local_provider(
                        session_id, first, base_url=base_url, model=preferred
                    )
                    fresh = self._ensure_live(
                        session_id, live.project_directory, configured["provider"], configured["model"],
                        live.scoped_models, document.get("local_llm", {}), executable, live.client.timeout,
                    )
                    state = fresh.client.get_state()
                    p, mid = self._model_label(state.get("model") if isinstance(state, dict) else {})
                    response_text = (
                        f"Switched Pi to `{p or configured['provider']}/{mid or configured['model']}`. "
                        f"Endpoint: `{configured['base_url']}`."
                    )
                else:
                    if len(args) >= 2:
                        target_provider, target_model = args[0], args[1]
                    elif "/" in first:
                        target_provider, target_model = first.split("/", 1)
                    else:
                        target_provider = str(document.get("provider") or "")
                        target_model = first
                        if not target_provider:
                            matches = [m for m in live.client.get_available_models() if self._model_label(m)[1] == target_model]
                            if len(matches) == 1:
                                target_provider, _ = self._model_label(matches[0])
                    if not target_provider:
                        raise ValueError("Use `/model provider/model-id` when the provider cannot be inferred.")
                    if target_provider.lower() in local_aliases:
                        current_local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
                        requested_provider = local_provider_id(target_provider)
                        base_url = str(current_local.get("base_url") or "") if str(current_local.get("provider") or "") == requested_provider else ""
                        configured, document = self.activate_local_provider(
                            session_id, target_provider, base_url=base_url, model=target_model
                        )
                        fresh = self._ensure_live(
                            session_id, live.project_directory, configured["provider"], configured["model"],
                            live.scoped_models, document.get("local_llm", {}), executable, live.client.timeout,
                        )
                        state = fresh.client.get_state()
                        p, mid = self._model_label(state.get("model") if isinstance(state, dict) else {})
                        response_text = f"Switched Pi model to `{p or configured['provider']}/{mid or configured['model']}`."
                    else:
                        selected = live.client.set_model(target_provider, target_model)
                        document["provider"] = target_provider
                        document["model"] = target_model
                        self.store.save(document)
                        live.provider = target_provider
                        live.model = target_model
                        p, mid = self._model_label(selected)
                        response_text = f"Switched Pi model to `{p or target_provider}/{mid or target_model}`."
        elif name == "scoped-models":
            if raw_args:
                document["scoped_models"] = raw_args
                self.store.save(document)
                self._close_live(session_id)
                response_text = f"Scoped model patterns set to `{raw_args}`. The next normal message starts Pi with the new scope."
            else:
                value = str(document.get("scoped_models") or "")
                response_text = "Scoped model patterns: " + (f"`{value}`" if value else "none (Pi's normal model catalog is used).")
        elif name == "settings":
            state = live.client.get_state()
            guard = document.get("context_guard") or {}
            if not args:
                response_text = (
                    "Current ComfyUI-Pi / Pi settings:\n"
                    f"- Model: `{self._model_label(state.get('model') or {})[0]}/{self._model_label(state.get('model') or {})[1]}`\n"
                    f"- Thinking: `{state.get('thinkingLevel', 'unknown')}`\n"
                    f"- Steering: `{state.get('steeringMode', 'unknown')}`\n"
                    f"- Follow-up: `{state.get('followUpMode', 'unknown')}`\n"
                    f"- Preemptive handoff: `{bool(guard.get('enabled', True))}` at `{float(guard.get('threshold', DEFAULT_HANDOFF_THRESHOLD))*100:.1f}%`\n"
                    "Use the sidebar Settings panel for provider/local-server controls."
                )
                ui_action = "open_settings"
            else:
                key = args[0].lower().replace("_", "-")
                value = args[1] if len(args) > 1 else ""
                if key == "thinking":
                    if not value:
                        response_text = "Available thinking levels: " + ", ".join(live.client.get_available_thinking_levels())
                    else:
                        live.client.set_thinking_level(value)
                        response_text = f"Thinking level set to `{value}`."
                elif key == "steering":
                    if value not in {"all", "one-at-a-time"}:
                        raise ValueError("Usage: `/settings steering all|one-at-a-time`")
                    live.client.set_steering_mode(value)
                    response_text = f"Steering mode set to `{value}`."
                elif key in {"follow-up", "followup"}:
                    if value not in {"all", "one-at-a-time"}:
                        raise ValueError("Usage: `/settings follow-up all|one-at-a-time`")
                    live.client.set_follow_up_mode(value)
                    response_text = f"Follow-up mode set to `{value}`."
                elif key == "handoff":
                    guard["threshold"] = clamp_threshold(value)
                    document["context_guard"] = guard
                    self.store.save(document)
                    response_text = f"Preemptive handoff threshold set to `{guard['threshold']*100:.1f}%`."
                else:
                    raise ValueError("Supported `/settings` keys in chat are: thinking, steering, follow-up, handoff.")
        elif name in {"login", "llama"}:
            if name == "llama":
                current_local = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
                base_url = str(current_local.get("base_url") or "")
                subcommand = args[0].lower() if args else "list"
                if subcommand.startswith(("http://", "https://")):
                    base_url = args[0]
                    subcommand = "list"
                elif subcommand in {"endpoint", "url"}:
                    if len(args) > 1:
                        base_url = args[1]
                    subcommand = "list"
                if subcommand in {"load", "unload", "download"}:
                    if len(args) < 2:
                        raise ValueError(f"Usage: `/llama {subcommand} <model-id>`")
                    model_id = args[1]
                    result = llama_router_action(subcommand, model_id, base_url=base_url, timeout=min(30.0, float(live.client.timeout)))
                    if subcommand == "load":
                        configured, document = self.activate_local_provider(
                            session_id, "llama.cpp", result["base_url"], model=model_id, models=[model_id]
                        )
                        response_text = f"llama.cpp router loaded `{model_id}` and selected `{configured['provider']}/{configured['model']}` for this chat."
                    elif subcommand == "unload":
                        if str(document.get("model") or "") == model_id:
                            document["model"] = ""
                            if isinstance(document.get("local_llm"), dict):
                                document["local_llm"]["model"] = ""
                            self.store.save(document)
                            self._close_live(session_id)
                        response_text = f"llama.cpp router unload requested for `{model_id}`."
                    else:
                        response_text = f"llama.cpp router download started for `{model_id}`. Run `/llama refresh` to update the model list."
                else:
                    listing = llama_router_models(base_url=base_url, reload=subcommand in {"refresh", "reload"})
                    base_url = str(listing.get("base_url") or base_url)
                    models = listing.get("models") or []
                    current = document.get("local_llm") if isinstance(document.get("local_llm"), dict) else {}
                    current.update({"kind": "llama.cpp", "base_url": base_url})
                    document["local_llm"] = current
                    self.store.save(document)
                    rows = [f"llama.cpp router: `{base_url}`", ""]
                    rows.extend(f"- `{item.get('id')}` — {item.get('status', 'unknown')}" for item in models[:120] if item.get("id"))
                    if not models:
                        rows.append("- No router models were reported.")
                    rows.extend(["", "Use `/llama load <model-id>`, `/llama unload <model-id>`, `/llama download <owner/repo:quant>`, or `/llama refresh`."])
                    response_text = "\n".join(rows)
            else:
                requested_kind = args[0] if args else ""
                if requested_kind.lower() in {"llama.cpp", "llamacpp", "llama-cpp", "llama_cpp", "ollama", "lm-studio", "lmstudio", "lm_studio", "vllm", "openai-compatible", "openai", "generic"}:
                    url_arg = args[1] if len(args) > 1 else ""
                    model_arg = args[2] if len(args) > 2 else ""
                    probe = probe_local_server(requested_kind, url_arg)
                    if not probe.get("available"):
                        response_text = str(probe.get("message") or "Local server was not detected.") + " Open Local LLM setup in Settings to edit the endpoint."
                        ui_action = "open_local_llm"
                    else:
                        models = list(probe.get("models") or [])
                        configured, document = self.activate_local_provider(
                            session_id, requested_kind, url_arg, model=model_arg, models=models
                        )
                        response_text = str(configured.get("message") or "Local provider configured.")
                else:
                    response_text = (
                        "Pi's subscription/OAuth `/login` selector exists only in its interactive TUI; RPC does not expose that credential UI. "
                        "ComfyUI-Pi can configure llama.cpp, Ollama, LM Studio, vLLM, and OpenAI-compatible local servers here. "
                        "For cloud providers, authenticate Pi once with its normal interactive `/login` or environment variable, then use `/model` here."
                    )
                    ui_action = "open_local_llm"
        elif name == "logout":
            document["provider"] = ""
            document["model"] = ""
            document["local_llm"] = {}
            self.store.save(document)
            self._close_live(session_id)
            response_text = (
                "Cleared this ComfyUI-Pi chat's provider/model override. Stored Pi credentials were not deleted because RPC does not expose Pi's interactive credential manager. "
                "Run Pi's interactive `/logout` if you need to remove a saved cloud credential."
            )
        elif name == "resume":
            if args:
                target = args[0]
                self.store.load(target)
                switch_session_id = target
                response_text = f"Switching the sidebar to saved chat `{target}`."
            else:
                sessions = self.store.list()[:50]
                response_text = "Saved ComfyUI-Pi chats:\n" + "\n".join(
                    f"- `{item['session_id']}` — {item.get('title', 'Chat')} ({item.get('message_count', 0)} messages)" for item in sessions
                )
        elif name == "new":
            created = self.store.create(raw_args or "New chat", document.get("project_directory", ""), document.get("provider", ""), document.get("model", ""))
            created["scoped_models"] = str(document.get("scoped_models") or "")
            created["local_llm"] = dict(document.get("local_llm") or {}) if isinstance(document.get("local_llm"), dict) else {}
            self.store.save(created)
            switch_session_id = str(created["session_id"])
            response_text = f"Created a new chat `{created['title']}`."
        elif name == "name":
            if not raw_args:
                response_text = f"Current chat name: `{document.get('title', 'Chat')}`"
            else:
                document["title"] = _safe_title(raw_args)
                self.store.save(document)
                try:
                    live.client.set_session_name(document["title"])
                except Exception:
                    pass
                response_text = f"Chat/session renamed to `{document['title']}`."
        elif name == "session":
            state = live.client.get_state()
            stats = live.client.get_session_stats()
            response_text = "Pi / ComfyUI-Pi session information:\n```json\n" + json.dumps({
                "chat_session_id": session_id,
                "chat_title": document.get("title"),
                "project_directory": document.get("project_directory"),
                "pi_state": state,
                "pi_stats": stats,
                "context_guard": document.get("context_guard", {}),
            }, ensure_ascii=False, indent=2)[:14_000] + "\n```"
        elif name == "tree":
            response_text = self._format_tree(live.client.get_tree())
        elif name == "trust":
            response_text = (
                "ComfyUI-Pi intentionally launches supervised Pi RPC with `--no-approve`, so `/trust` cannot silently enable project-local executable resources in this embedded agent. "
                "This preserves the plugin's security boundary. Use standalone Pi's interactive `/trust` if you intentionally want to persist a trust decision; ComfyUI-Pi will continue to load only explicitly selected/dynamic resources."
            )
        elif name == "fork":
            if not args:
                points = live.client.get_fork_messages()
                response_text = "Available Pi fork points:\n" + "\n".join(
                    f"- `{item.get('entryId')}` — {str(item.get('text') or '')[:180]}" for item in points[:80]
                )
            else:
                result = live.client.fork(args[0])
                if result.get("cancelled"):
                    response_text = "Pi cancelled the fork."
                else:
                    clone = self._duplicate_visible_session(document, "Fork: " + document.get("title", "Chat"))
                    switch_session_id = str(clone["session_id"])
                    self._move_live_session(session_id, switch_session_id, live)
                    response_text = f"Forked Pi at entry `{args[0]}` and created sidebar chat `{switch_session_id}`."
        elif name == "clone":
            result = live.client.clone()
            if result.get("cancelled"):
                response_text = "Pi cancelled the clone."
            else:
                clone = self._duplicate_visible_session(document, "Clone: " + document.get("title", "Chat"))
                switch_session_id = str(clone["session_id"])
                self._move_live_session(session_id, switch_session_id, live)
                response_text = f"Cloned the active Pi branch into sidebar chat `{switch_session_id}`."
        elif name == "compact":
            routed = build_dynamic_integration_context(workflow=workflow, message=raw_args or "manual context handoff")
            guidance = build_request_guidance(raw_args or "continue current work", workflow=workflow)
            routed = dict(routed)
            routed["loaded_skills"] = guidance.get("loaded_skills", [])
            document, handoff = self._manual_handoff(
                session_id, live, document, project_context, workflow_summary, workflow_path,
                routed, threshold, max_handoff_chars, focus=raw_args,
            )
            response_text = f"Created and ingested ComfyUI-Pi handoff `{handoff.get('path')}` and reset Pi context."
        elif name == "copy":
            last = next((str(item.get("content") or "") for item in reversed(document.get("messages") or []) if isinstance(item, dict) and item.get("role") == "assistant"), "")
            response_text = last or "There is no assistant reply to copy yet."
            ui_action = "copy_text"
        elif name == "export":
            exports = get_comfy_user_directory() / "pi-agent" / "exports"
            exports.mkdir(parents=True, exist_ok=True)
            output = Path(raw_args).expanduser() if raw_args else exports / f"{_safe_session_id(session_id)}.html"
            if not output.is_absolute():
                output = exports / output
            result = live.client.export_html(str(output.resolve()))
            response_text = f"Exported Pi session to `{result.get('path') or output.resolve()}`."
        elif name == "import":
            if not raw_args:
                raise ValueError("Usage: `/import <session.jsonl>`")
            path = Path(raw_args).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Pi session file not found: {path}")
            result = live.client.switch_session(str(path))
            live.context_signature = None
            live.handoff_ingested = False
            response_text = "Imported Pi session." if not result.get("cancelled") else "Pi cancelled the session import."
        elif name == "share":
            exports = get_comfy_user_directory() / "pi-agent" / "exports"
            exports.mkdir(parents=True, exist_ok=True)
            expected_html = (exports / f"{_safe_session_id(session_id)}-share.html").resolve()
            export_result = live.client.export_html(str(expected_html))
            html = Path(str(export_result.get("path") or expected_html))
            gh = subprocess.run(["gh", "--version"], capture_output=True, text=True, check=False) if shutil.which("gh") else None
            if gh and gh.returncode == 0 and html.is_file():
                shared = subprocess.run(["gh", "gist", "create", str(html)], capture_output=True, text=True, check=False)
                response_text = shared.stdout.strip() if shared.returncode == 0 else f"Local export created at `{html}` but GitHub sharing failed: {shared.stderr.strip()}"
            else:
                response_text = f"Created a local share-ready export at `{html}`. Install/authenticate GitHub CLI (`gh`) to have `/share` upload it as a secret gist."
        elif name == "reload":
            self._close_live(session_id)
            response_text = "Stopped the current lean Pi RPC process. The next message will start a fresh process with current provider, local-server, scoped-model, and dynamic-context configuration."
        elif name == "changelog":
            version_text = "unknown"
            try:
                proc = subprocess.run([live.executable, "--version"], capture_output=True, text=True, timeout=5, check=False)
                version_text = (proc.stdout or proc.stderr).strip() or "unknown"
            except Exception:
                pass
            response_text = f"Installed Pi: `{version_text}`\n\nComfyUI-Pi release notes are in `RELEASE_NOTES.md`."
        elif name == "quit":
            self._close_live(session_id)
            response_text = "Stopped Pi for this chat. The conversation is still saved; sending another normal message will start Pi again."
        else:
            response_text = f"`/{name}` is recognized but has no ComfyUI-Pi bridge yet."

        document = self.store.append(session_id, "assistant", response_text, slash_command=name)
        return {
            "ok": True,
            "session": document,
            "message": document["messages"][-1],
            "runtime": discover_pi(executable).to_dict(),
            "slash_command": name,
            "ui_action": ui_action,
            "switch_session_id": switch_session_id,
            "handoff": handoff,
            "context_guard": document.get("context_guard", {}),
        }

    def _ensure_live(
        self,
        session_id: str,
        project_directory: str,
        provider: str,
        model: str,
        scoped_models: str,
        local_llm: dict[str, Any] | None,
        executable: str,
        timeout: int,
    ) -> _LiveSession:
        status = discover_pi(executable)
        if not status.available or not status.executable:
            raise RuntimeError(status.message)
        resolved_executable = str(status.executable)
        local_config = local_llm if isinstance(local_llm, dict) else {}
        local_signature = hashlib.sha256(json.dumps(local_config, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        with self._guard:
            live = self._live.get(session_id)
            changed = bool(live and (
                live.project_directory != project_directory
                or live.provider != provider
                or live.model != model
                or live.scoped_models != scoped_models
                or live.local_signature != local_signature
                or live.executable != resolved_executable
            ))
            if changed and live:
                self._live.pop(session_id, None)
                live.client.close()
                live = None
            if live is None:
                client = PiRpcClient(
                    resolved_executable,
                    project_dir=project_directory,
                    provider=provider,
                    model=model,
                    timeout=timeout,
                    scoped_models=scoped_models,
                    env_overrides=runtime_environment(local_config),
                )
                live = _LiveSession(
                    client=client,
                    project_directory=project_directory,
                    provider=provider,
                    model=model,
                    scoped_models=scoped_models,
                    local_signature=local_signature,
                    executable=resolved_executable,
                    lock=threading.Lock(),
                    context_signature=None,
                    handoff_ingested=False,
                )
                self._live[session_id] = live
            else:
                live.client.timeout = max(10, int(timeout))
            return live

    @staticmethod
    def _clean_history(messages: list[dict[str, Any]], max_chars: int = 12_000) -> str:
        """Render a bounded user-visible transcript without hidden injected context/tool output."""
        parts: list[str] = []
        total = 0
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").upper()
            if role not in {"USER", "ASSISTANT"}:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            block = f"{role}:\n{content}\n"
            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    parts.append(block[-remaining:])
                break
            parts.append(block)
            total += len(block)
        parts.reverse()
        return "\n".join(parts)

    @staticmethod
    def build_agent_message(
        message: str,
        workflow: Any = None,
        project_context: str = "",
        workflow_context_path: str = "",
        routed_context: dict[str, Any] | None = None,
        guidance: dict[str, Any] | None = None,
        include_scope_context: bool = True,
        conversation_history: str = "",
    ) -> str:
        guidance = guidance if isinstance(guidance, dict) else build_request_guidance(message, workflow=workflow)
        sections = [
            "You are being instructed from the ComfyUI Pi Agent sidebar chat.",
            guidance.get("task_envelope", "CURRENT JOB: " + str(message or "")),
        ]
        if include_scope_context:
            sections.insert(0, guidance.get("core_contract", ""))
        if conversation_history.strip():
            sections.append(
                "Recent clean sidebar conversation (user-visible messages only; hidden integration context is intentionally not replayed):\n"
                + conversation_history.strip()
            )
        if include_scope_context:
            skill_context = str(guidance.get("skill_context") or "")
            if skill_context:
                selected = ", ".join(str(item.get("name")) for item in guidance.get("loaded_skills", []) if isinstance(item, dict))
                sections.append(
                    "ComfyUI-Pi dynamically selected task procedures"
                    + (f" ({selected})" if selected else "")
                    + ":\n" + skill_context
                )
            if project_context.strip():
                project_text = project_context.strip()
                sections.append("Project context (bounded):\n" + project_text[:20_000])
                if len(project_text) > 20_000:
                    sections.append("Project context was truncated because it exceeded the normal chat context budget.")
            routed = routed_context if isinstance(routed_context, dict) else build_dynamic_integration_context(workflow=workflow, message=message)
            integration_context = str(routed.get("context") or "")
            if integration_context:
                loaded = ", ".join(str(item.get("id")) for item in routed.get("loaded_integrations", []))
                sections.append(
                    "ComfyUI-Pi dynamically loaded node-pack knowledge"
                    + (f" ({loaded})" if loaded else "")
                    + ":\n"
                    + integration_context
                )
            if workflow not in (None, "", {}):
                sections.append("Current ComfyUI workflow compact digest:\n" + _compact_workflow_summary(workflow))
                if workflow_context_path:
                    sections.append(
                        "Full current workflow JSON is available locally at:\n"
                        + workflow_context_path
                        + "\nRead that file only when graph-level details are needed for this request. "
                          "Do not read it merely because it is available."
                    )
        sections.append("User message:\n" + str(message or ""))
        return "\n\n".join(sections)

    @staticmethod
    def _scope_signature(
        routed: dict[str, Any],
        project_context: str,
        workflow_summary: str,
        guidance: dict[str, Any] | None = None,
    ) -> str:
        guidance = guidance if isinstance(guidance, dict) else {}
        material = json.dumps({
            "integrations": routed.get("loaded_integrations", []),
            "integration_context": routed.get("context", ""),
            "skills": guidance_signature(guidance),
            "project_context": str(project_context or "")[:20_000],
            "workflow_summary": workflow_summary,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _handoff_summarizer(
        executable: str,
        project_directory: str,
        provider: str,
        model: str,
        scoped_models: str,
        local_llm: dict[str, Any] | None,
        timeout: int,
    ):
        """Return a fresh-process summarizer so the near-full session is never used to summarize itself."""
        def summarize(source_path: Path, max_chars: int) -> str:
            client = PiRpcClient(
                executable,
                project_dir=project_directory,
                provider=provider,
                model=model,
                timeout=max(30, min(int(timeout), 180)),
                scoped_models=scoped_models,
                env_overrides=runtime_environment(local_llm),
            )
            try:
                prompt = (
                    "You are ComfyUI-Pi's continuity handoff compiler. Read the JSON source file at the path below. "
                    "Create a concise Markdown handoff for another agent instance that must continue the same work without "
                    "re-reading the whole conversation. Preserve concrete goals, user constraints, decisions, completed work, "
                    "current artifacts/paths, failures/blockers, and the next most useful actions. Do not copy the transcript. "
                    "Do not embed large workflow JSON, logs, node-pack manuals, or generated media; reference their paths/digests. "
                    "Do not include secrets. Use these headings: Primary Objective; Non-negotiable Constraints; Decisions and "
                    "Current State; Completed Work; Active Artifacts and Paths; Open Problems / Risks; Next Actions; Dynamic "
                    "Context to Reload Only If Needed. Keep the complete Markdown under "
                    f"{max_chars} characters. Return only the Markdown handoff.\n\nSource JSON: {source_path.resolve()}"
                )
                result = client.prompt(prompt)
                return str(result.get("text") or "").strip()
            finally:
                client.close()
        return summarize

    @staticmethod
    def _pressure_from_prompt_result(prompt_result: dict[str, Any], threshold: float):
        """Prefer Pi's exact RPC contextUsage estimate; fall back to assistant usage."""
        direct_tokens = 0
        try:
            direct_tokens = int(prompt_result.get("context_tokens") or 0)
        except Exception:
            direct_tokens = 0
        usage = {"totalTokens": direct_tokens} if direct_tokens > 0 else prompt_result.get("usage")
        return context_pressure(usage, prompt_result.get("context_window"), threshold)

    def _preemptive_handoff(
        self,
        session_id: str,
        live: _LiveSession,
        document: dict[str, Any],
        prompt_result: dict[str, Any],
        project_context: str,
        workflow_summary: str,
        workflow_path: str,
        routed: dict[str, Any],
        threshold: float,
        max_chars: int,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        pressure = self._pressure_from_prompt_result(prompt_result, threshold)
        pressure_dict = pressure.to_dict()
        document = self.store.update_context_guard(session_id, pressure_dict)
        if not pressure.should_handoff:
            return document, None

        summarizer = self._handoff_summarizer(
            live.executable,
            live.project_directory,
            live.provider,
            live.model,
            live.scoped_models,
            document.get("local_llm", {}),
            live.client.timeout,
        )
        handoff = create_handoff(
            session_id=session_id,
            document=document,
            pressure=pressure,
            project_context=project_context,
            workflow_summary=workflow_summary,
            workflow_context_path=workflow_path,
            routed_context=routed,
            max_chars=max_chars,
            summarizer=summarizer,
        )

        # Hard reset instead of Pi's built-in compaction. Then silently ingest the durable
        # handoff once. The user-visible transcript stays in ComfyUI-Pi's JSON store.
        live.client.new_session()
        handoff_text = Path(str(handoff["path"])).read_text(encoding="utf-8")
        bootstrap = live.client.prompt(handoff_bootstrap_prompt(str(handoff["path"]), handoff_text=handoff_text))
        ack = str(bootstrap.get("text") or "").strip().upper() == "HANDOFF_READY"
        post_pressure = self._pressure_from_prompt_result(bootstrap, threshold).to_dict()
        handoff = dict(handoff)
        # Successful prompt delivery means the bounded handoff is now literally in the fresh
        # Pi context even if a weak model fails to obey the requested acknowledgement string.
        handoff["ingested"] = True
        handoff["bootstrap_acknowledged"] = ack
        handoff["reset_method"] = "new_session"
        handoff["trigger_pressure"] = pressure_dict
        handoff["post_reset_pressure"] = post_pressure
        document = self.store.update_context_guard(session_id, post_pressure, handoff=handoff)
        # The next user turn should inject the current bounded workflow/integration scope again,
        # but should not replay old visible history because the handoff already captured it.
        live.context_signature = None
        live.handoff_ingested = True
        return document, handoff

    def send(
        self,
        session_id: str,
        message: str,
        project_directory: str = "",
        provider: str = "",
        model: str = "",
        scoped_models: str = "",
        local_llm: dict[str, Any] | None = None,
        executable: str = "",
        timeout: int = 180,
        workflow: Any = None,
        project_context: str = "",
        preemptive_handoff: bool = True,
        handoff_threshold: float | int | str = DEFAULT_HANDOFF_THRESHOLD,
        handoff_max_chars: int | str = DEFAULT_HANDOFF_MAX_CHARS,
    ) -> dict[str, Any]:
        text = str(message or "").strip()
        if not text:
            raise ValueError("Message cannot be empty.")
        threshold = clamp_threshold(handoff_threshold)
        max_handoff_chars = clamp_handoff_chars(handoff_max_chars)
        document = self.store.update_config(
            session_id, project_directory, provider, model,
            scoped_models=scoped_models,
            local_llm=local_llm,
            preemptive_handoff=preemptive_handoff,
            handoff_threshold=threshold,
            handoff_max_chars=max_handoff_chars,
        )
        document = self.store.append(session_id, "user", text)
        try:
            # Always launch Pi from the normalized, persisted provider/model state.
            # This is especially important when opening a chat created by v0.1.9,
            # which could accidentally store an endpoint URL in the provider field.
            # update_config() repairs that state before we reach this point.
            live = self._ensure_live(
                session_id, project_directory, str(document.get("provider") or ""), str(document.get("model") or ""),
                str(document.get("scoped_models") or ""),
                document.get("local_llm", {}),
                executable, timeout,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            document = self.store.append(session_id, "assistant", error, error=True)
            return {
                "ok": False,
                "session": document,
                "message": document["messages"][-1],
                "runtime": discover_pi(executable).to_dict(),
                "error": error,
            }
        workflow_path = ""
        if workflow not in (None, "", {}):
            try:
                path = _workflow_context_path(session_id)
                atomic_write_json(path, workflow)
                workflow_path = str(path.resolve())
            except Exception:
                workflow_path = ""
        parsed_command = parse_slash_command(text)
        workflow_summary = _compact_workflow_summary(workflow) if workflow not in (None, "", {}) else ""
        if parsed_command is not None:
            with live.lock:
                try:
                    handled = self._handle_builtin_command(
                        session_id=session_id,
                        text=text,
                        parsed=parsed_command,
                        document=document,
                        live=live,
                        project_context=project_context,
                        workflow_summary=workflow_summary,
                        workflow_path=workflow_path,
                        workflow=workflow,
                        threshold=threshold,
                        max_handoff_chars=max_handoff_chars,
                        executable=executable,
                    )
                    if handled is not None:
                        return handled
                    # Pi RPC itself can expand extension commands, prompt templates, and skills.
                    # Unknown slash commands are passed through *raw* instead of being wrapped in
                    # ComfyUI-Pi's agent envelope, so explicitly loaded Pi commands retain their
                    # native semantics.
                    result = live.client.prompt(text)
                    assistant_text = str(result.get("text") or "").strip() or f"Pi handled `/{parsed_command[0]}` without a text response."
                    document = self.store.append(session_id, "assistant", assistant_text, slash_command=parsed_command[0], pi_passthrough=True)
                    return {
                        "ok": True,
                        "session": document,
                        "message": document["messages"][-1],
                        "runtime": discover_pi(executable).to_dict(),
                        "slash_command": parsed_command[0],
                        "pi_passthrough": True,
                        "context_guard": document.get("context_guard", {}),
                    }
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    document = self.store.append(session_id, "assistant", error, error=True, slash_command=parsed_command[0])
                    return {
                        "ok": False,
                        "session": document,
                        "message": document["messages"][-1],
                        "runtime": discover_pi(executable).to_dict(),
                        "error": error,
                        "slash_command": parsed_command[0],
                    }
        routed = build_dynamic_integration_context(workflow=workflow, message=text)
        guidance = build_request_guidance(text, workflow=workflow)
        routed = dict(routed)
        routed["loaded_skills"] = guidance.get("loaded_skills", [])
        signature = self._scope_signature(routed, project_context, workflow_summary, guidance=guidance)
        with live.lock:
            try:
                scope_changed = live.context_signature != signature
                # Pi RPC is stateful. When specialized/project/workflow context changes, reset
                # its in-memory conversation so old injected node-pack knowledge does not linger.
                # Rehydrate only the bounded clean transcript that the user can see.
                conversation_history = ""
                if scope_changed:
                    if live.context_signature is not None:
                        live.client.new_session()
                    if not live.handoff_ingested:
                        prior_messages = document.get("messages", [])[:-1]
                        if isinstance(prior_messages, list):
                            conversation_history = self._clean_history(prior_messages)
                    live.context_signature = signature
                    live.handoff_ingested = False
                prompt = self.build_agent_message(
                    text,
                    workflow=workflow,
                    project_context=project_context,
                    workflow_context_path=workflow_path,
                    routed_context=routed,
                    guidance=guidance,
                    include_scope_context=scope_changed,
                    conversation_history=conversation_history,
                )
                result = live.client.prompt(prompt)
                assistant_text = str(result.get("text") or "").strip()
                if not assistant_text:
                    assistant_text = "Pi finished without returning a text response."
                document = self.store.append(session_id, "assistant", assistant_text)
                assistant_message = document["messages"][-1]
                handoff = None
                if preemptive_handoff:
                    document, handoff = self._preemptive_handoff(
                        session_id=session_id,
                        live=live,
                        document=document,
                        prompt_result=result,
                        project_context=project_context,
                        workflow_summary=workflow_summary,
                        workflow_path=workflow_path,
                        routed=routed,
                        threshold=threshold,
                        max_chars=max_handoff_chars,
                    )
                else:
                    pressure = self._pressure_from_prompt_result(result, threshold)
                    document = self.store.update_context_guard(session_id, pressure.to_dict())
                return {
                    "ok": True,
                    "session": document,
                    "message": assistant_message,
                    "runtime": discover_pi(executable).to_dict(),
                    "context_guard": document.get("context_guard", {}),
                    "handoff": handoff,
                    "pi_auto_compaction_disabled": bool(result.get("pi_auto_compaction_disabled")),
                    "pi_auto_compaction_warning": result.get("pi_auto_compaction_warning", ""),
                }
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                document = self.store.append(session_id, "assistant", error, error=True)
                return {
                    "ok": False,
                    "session": document,
                    "message": document["messages"][-1],
                    "runtime": discover_pi(executable).to_dict(),
                    "error": error,
                }


CHAT_MANAGER = ChatRuntimeManager()
