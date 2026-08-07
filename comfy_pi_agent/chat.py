from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compat import get_comfy_user_directory
from .io_utils import atomic_write_json
from .pi_runtime import PiRpcClient, discover_pi
from .integrations.router import build_dynamic_integration_context
from .workflow import analyze_workflow
from .agent_guidance import build_request_guidance, guidance_signature
from .context_handoff import (
    DEFAULT_HANDOFF_MAX_CHARS,
    DEFAULT_HANDOFF_THRESHOLD,
    clamp_handoff_chars,
    clamp_threshold,
    context_pressure,
    create_handoff,
    handoff_bootstrap_prompt,
)


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
        preemptive_handoff: bool = True,
        handoff_threshold: float | int | str = DEFAULT_HANDOFF_THRESHOLD,
        handoff_max_chars: int | str = DEFAULT_HANDOFF_MAX_CHARS,
    ) -> dict[str, Any]:
        document = self.load(session_id)
        document["project_directory"] = str(project_directory or "")
        document["provider"] = str(provider or "")
        document["model"] = str(model or "")
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

    def _ensure_live(
        self,
        session_id: str,
        project_directory: str,
        provider: str,
        model: str,
        executable: str,
        timeout: int,
    ) -> _LiveSession:
        status = discover_pi(executable)
        if not status.available or not status.executable:
            raise RuntimeError(status.message)
        resolved_executable = str(status.executable)
        with self._guard:
            live = self._live.get(session_id)
            changed = bool(live and (
                live.project_directory != project_directory
                or live.provider != provider
                or live.model != model
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
                )
                live = _LiveSession(
                    client=client,
                    project_directory=project_directory,
                    provider=provider,
                    model=model,
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
            preemptive_handoff=preemptive_handoff,
            handoff_threshold=threshold,
            handoff_max_chars=max_handoff_chars,
        )
        document = self.store.append(session_id, "user", text)
        try:
            live = self._ensure_live(session_id, project_directory, provider, model, executable, timeout)
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
        routed = build_dynamic_integration_context(workflow=workflow, message=text)
        guidance = build_request_guidance(text, workflow=workflow)
        routed = dict(routed)
        routed["loaded_skills"] = guidance.get("loaded_skills", [])
        workflow_summary = _compact_workflow_summary(workflow) if workflow not in (None, "", {}) else ""
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
