from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .compat import get_comfy_user_directory
from .integrations.router import build_dynamic_integration_context
from .agent_guidance import build_request_guidance
from .io_utils import load_json


@dataclass
class PiRuntimeStatus:
    available: bool
    executable: str | None
    source: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_pi(explicit: str = "") -> PiRuntimeStatus:
    candidates: list[tuple[str, str]] = []
    if explicit.strip():
        candidates.append((explicit.strip(), "explicit"))
    env = os.environ.get("PI_AGENT_EXECUTABLE", "").strip()
    if env:
        candidates.append((env, "PI_AGENT_EXECUTABLE"))
    found = shutil.which("pi")
    if found:
        candidates.append((found, "PATH"))
    for candidate, source in candidates:
        path = shutil.which(candidate) or candidate
        if Path(path).expanduser().is_file() or shutil.which(path):
            return PiRuntimeStatus(True, str(path), source, "Pi executable found.")
    return PiRuntimeStatus(False, None, "none", "Pi is not installed or configured. Non-agent project tools still work. Set PI_AGENT_EXECUTABLE or install Pi to enable LLM reasoning.")


def _extract_message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return ""


def build_pi_command(
    executable: str,
    provider: str = "",
    model: str = "",
    scoped_models: str = "",
) -> list[str]:
    """Build the deliberately lean Pi RPC command used by ComfyUI-Pi.

    Pi normally discovers project/global context files, skills, extensions, prompt templates,
    and themes. ComfyUI-Pi disables that discovery for its supervised RPC subprocess so the
    LLM context starts clean. Relevant ComfyUI/node-pack guidance is selected later by the
    dynamic integration router and injected only when a request or attached workflow matches.
    """
    command = [
        executable,
        "--mode", "rpc",
        "--no-approve",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-session",
    ]
    if provider.strip():
        command += ["--provider", provider.strip()]
    if model.strip():
        command += ["--model", model.strip()]
    if scoped_models.strip():
        command += ["--models", scoped_models.strip()]
    return command


class PiRpcClient:
    def __init__(
        self,
        executable: str,
        project_dir: str = "",
        provider: str = "",
        model: str = "",
        timeout: int = 180,
        scoped_models: str = "",
        env_overrides: dict[str, str] | None = None,
    ):
        self.timeout = max(10, int(timeout))
        command = build_pi_command(executable, provider=provider, model=model, scoped_models=scoped_models)
        cwd = Path(project_dir).expanduser().resolve() if project_dir.strip() else get_comfy_user_directory()
        cwd.mkdir(parents=True, exist_ok=True)
        process_env = os.environ.copy()
        for key, value in (env_overrides or {}).items():
            if key and value is not None:
                process_env[str(key)] = str(value)
        self.process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=process_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stderr_lines: queue.Queue[str] = queue.Queue()
        self.stderr_history: list[str] = []
        self._stderr_lock = threading.Lock()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        # Do not let the first real chat prompt double as an RPC startup probe. Wait
        # until Pi is actually accepting JSONL commands, and surface startup stderr if
        # it exits because a provider/model/configuration is invalid.
        self._wait_until_rpc_ready(timeout=min(30.0, max(10.0, float(self.timeout))))
        # ComfyUI-Pi owns long-session context lifecycle. Disable Pi's built-in auto
        # compactor so it cannot race the external handoff/reset policy. Older Pi builds
        # that do not expose this RPC command remain usable, but the status is reported.
        self.auto_compaction_disabled = False
        self.auto_compaction_warning = ""
        try:
            self.set_auto_compaction(False)
            self.auto_compaction_disabled = True
        except Exception as exc:
            self.auto_compaction_warning = f"Could not disable Pi auto-compaction: {type(exc).__name__}: {exc}"

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for raw in self.process.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                self.events.put({"type": "protocol_warning", "line": line})

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for raw in self.process.stderr:
            line = raw.rstrip("\r\n")
            self.stderr_lines.put(line)
            with self._stderr_lock:
                self.stderr_history.append(line)
                if len(self.stderr_history) > 120:
                    del self.stderr_history[:-120]

    def _exit_diagnostic(self, prefix: str = "Pi exited") -> RuntimeError:
        code = self.process.poll()
        with self._stderr_lock:
            lines = [line for line in self.stderr_history[-20:] if line.strip()]
        detail = "\n".join(lines).strip()
        message = f"{prefix} (exit code {code})." if code is not None else prefix
        if detail:
            message += "\nPi stderr:\n" + detail
        return RuntimeError(message)

    def _wait_until_rpc_ready(self, timeout: float = 30.0) -> None:
        try:
            self.command({"type": "get_state"}, timeout=max(2.0, float(timeout)))
        except Exception as exc:
            if self.process.poll() is not None:
                raise self._exit_diagnostic("Pi exited during RPC startup") from exc
            raise RuntimeError(f"Pi RPC did not become ready: {exc}") from exc

    def send(self, payload: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            raise self._exit_diagnostic("Pi exited before accepting the command")
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def command(self, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
        """Send a non-prompt RPC command and wait for its correlated response."""
        request_id = str(payload.get("id") or f"comfy-cmd-{int(time.time() * 1000)}")
        body = dict(payload)
        body["id"] = request_id
        self.send(body)
        deadline = time.monotonic() + max(1.0, float(timeout))
        while time.monotonic() < deadline:
            if self.process.poll() is not None and self.events.empty():
                raise self._exit_diagnostic(f"Pi exited while handling RPC command {body.get('type')}")
            try:
                event = self.events.get(timeout=0.2)
            except queue.Empty:
                continue
            if event.get("type") == "response" and event.get("id") == request_id:
                if not event.get("success"):
                    raise RuntimeError(str(event))
                return event
        raise TimeoutError(f"Pi RPC command {body.get('type')} did not respond within {timeout} seconds.")

    def new_session(self) -> dict[str, Any]:
        """Reset Pi's in-memory conversation while keeping the RPC process alive."""
        return self.command({"type": "new_session"})

    def set_auto_compaction(self, enabled: bool) -> dict[str, Any]:
        """Enable/disable Pi's own compactor. ComfyUI-Pi normally keeps this disabled."""
        return self.command({"type": "set_auto_compaction", "enabled": bool(enabled)})

    def get_state(self) -> dict[str, Any]:
        response = self.command({"type": "get_state"})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def get_messages(self) -> list[dict[str, Any]]:
        response = self.command({"type": "get_messages"})
        data = response.get("data")
        messages = data.get("messages") if isinstance(data, dict) else []
        return messages if isinstance(messages, list) else []

    def get_session_stats(self) -> dict[str, Any]:
        """Return Pi session statistics when supported by the installed RPC version."""
        response = self.command({"type": "get_session_stats"})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def get_available_models(self) -> list[dict[str, Any]]:
        response = self.command({"type": "get_available_models"})
        data = response.get("data")
        models = data.get("models") if isinstance(data, dict) else []
        return models if isinstance(models, list) else []

    def set_model(self, provider: str, model_id: str) -> dict[str, Any]:
        response = self.command({"type": "set_model", "provider": str(provider), "modelId": str(model_id)})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def cycle_model(self) -> dict[str, Any] | None:
        response = self.command({"type": "cycle_model"})
        data = response.get("data")
        return data if isinstance(data, dict) else None

    def get_available_thinking_levels(self) -> list[str]:
        response = self.command({"type": "get_available_thinking_levels"})
        data = response.get("data")
        levels = data.get("levels") if isinstance(data, dict) else []
        return [str(item) for item in levels] if isinstance(levels, list) else []

    def set_thinking_level(self, level: str) -> dict[str, Any]:
        return self.command({"type": "set_thinking_level", "level": str(level)})

    def set_steering_mode(self, mode: str) -> dict[str, Any]:
        return self.command({"type": "set_steering_mode", "mode": str(mode)})

    def set_follow_up_mode(self, mode: str) -> dict[str, Any]:
        return self.command({"type": "set_follow_up_mode", "mode": str(mode)})

    def compact(self, custom_instructions: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "compact"}
        if custom_instructions.strip():
            payload["customInstructions"] = custom_instructions.strip()
        response = self.command(payload, timeout=max(30.0, float(self.timeout)))
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def export_html(self, output_path: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "export_html"}
        if output_path.strip():
            payload["outputPath"] = output_path.strip()
        response = self.command(payload, timeout=max(10.0, float(self.timeout)))
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def switch_session(self, session_path: str) -> dict[str, Any]:
        response = self.command({"type": "switch_session", "sessionPath": str(session_path)})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def get_fork_messages(self) -> list[dict[str, Any]]:
        response = self.command({"type": "get_fork_messages"})
        data = response.get("data")
        messages = data.get("messages") if isinstance(data, dict) else []
        return messages if isinstance(messages, list) else []

    def fork(self, entry_id: str) -> dict[str, Any]:
        response = self.command({"type": "fork", "entryId": str(entry_id)})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def clone(self) -> dict[str, Any]:
        response = self.command({"type": "clone"})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def get_tree(self) -> dict[str, Any]:
        response = self.command({"type": "get_tree"})
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def get_last_assistant_text(self) -> str:
        response = self.command({"type": "get_last_assistant_text"})
        data = response.get("data")
        return str(data.get("text") or "") if isinstance(data, dict) else ""

    def set_session_name(self, name: str) -> dict[str, Any]:
        return self.command({"type": "set_session_name", "name": str(name)})

    def get_commands(self) -> list[dict[str, Any]]:
        response = self.command({"type": "get_commands"})
        data = response.get("data")
        commands = data.get("commands") if isinstance(data, dict) else []
        return commands if isinstance(commands, list) else []

    def prompt(self, message: str) -> dict[str, Any]:
        request_id = f"comfy-{int(time.time() * 1000)}"
        self.send({"id": request_id, "type": "prompt", "message": message})
        deadline = time.monotonic() + self.timeout
        final_text = ""
        streamed: list[str] = []
        reasoning_stream: list[str] = []
        activity: list[dict[str, Any]] = []
        event_log = []
        accepted = False
        final_message: dict[str, Any] = {}
        while time.monotonic() < deadline:
            if self.process.poll() is not None and self.events.empty():
                break
            try:
                event = self.events.get(timeout=0.2)
            except queue.Empty:
                continue
            event_log.append(event)
            if event.get("type") == "response" and event.get("id") == request_id:
                accepted = bool(event.get("success"))
                if not accepted:
                    raise RuntimeError(str(event))
            elif event.get("type") == "message_update":
                delta = event.get("assistantMessageEvent", {})
                delta_type = str(delta.get("type") or "") if isinstance(delta, dict) else ""
                if delta_type == "text_delta":
                    streamed.append(str(delta.get("delta", "")))
                elif delta_type in {"thinking_delta", "reasoning_delta"}:
                    reasoning_stream.append(str(delta.get("delta", "")))
                elif delta_type in {"toolcall_start", "toolcall_end"}:
                    tool_call = delta.get("toolCall") if isinstance(delta.get("toolCall"), dict) else {}
                    activity.append({
                        "type": delta_type,
                        "name": str(tool_call.get("name") or delta.get("name") or "tool"),
                        "arguments": tool_call.get("arguments") or tool_call.get("input") or {},
                    })
            elif event.get("type") in {"tool_execution_start", "tool_execution_update", "tool_execution_end"}:
                activity.append({
                    "type": str(event.get("type") or "tool"),
                    "name": str(event.get("toolName") or event.get("name") or event.get("tool") or "tool"),
                    "tool_call_id": str(event.get("toolCallId") or event.get("id") or ""),
                    "is_error": bool(event.get("isError", False)),
                    "result": event.get("result") if event.get("type") == "tool_execution_end" else None,
                })
            elif event.get("type") == "message_end":
                message_obj = event.get("message")
                if isinstance(message_obj, dict) and message_obj.get("role") == "assistant":
                    final_message = message_obj
                    text = _extract_message_text(message_obj)
                    if text:
                        final_text = text
            elif event.get("type") == "agent_settled":
                break
        else:
            try:
                self.send({"type": "abort"})
            except Exception:
                pass
            raise TimeoutError(f"Pi did not settle within {self.timeout} seconds.")
        if not final_text:
            final_text = "".join(streamed).strip()
        # Pi exposes an authoritative final-text RPC specifically so embedders do not
        # have to guess whether a provider emitted an unusual stream/event shape. Use it
        # before declaring that a successful turn returned no visible answer.
        if not final_text and accepted:
            try:
                final_text = self.get_last_assistant_text().strip()
            except Exception:
                final_text = ""
        if not final_text and accepted:
            try:
                for candidate in reversed(self.get_messages()):
                    if isinstance(candidate, dict) and candidate.get("role") == "assistant":
                        final_text = _extract_message_text(candidate).strip()
                        if final_text:
                            if not final_message:
                                final_message = candidate
                            break
            except Exception:
                pass
        reasoning = "".join(reasoning_stream).strip()
        if not reasoning and isinstance(final_message, dict):
            content = final_message.get("content")
            if isinstance(content, list):
                blocks: list[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("type") or "") in {"thinking", "reasoning"}:
                        value = item.get("thinking") or item.get("reasoning") or item.get("text") or item.get("content") or ""
                        if value:
                            blocks.append(str(value))
                reasoning = "\n".join(blocks).strip()
        stderr = []
        while not self.stderr_lines.empty():
            stderr.append(self.stderr_lines.get())
        state: dict[str, Any] = {}
        try:
            state = self.get_state()
        except Exception:
            state = {}
        model_state = state.get("model") if isinstance(state, dict) else {}
        context_window = model_state.get("contextWindow", 0) if isinstance(model_state, dict) else 0
        usage = final_message.get("usage") if isinstance(final_message, dict) else {}

        # Current Pi RPC builds expose the exact context estimate used by Pi's own
        # compaction/footer logic as get_session_stats.contextUsage. Prefer that value
        # when available; assistant usage + model contextWindow remains the fallback for
        # older compatible Pi builds.
        session_stats: dict[str, Any] = {}
        context_tokens = 0
        try:
            session_stats = self.get_session_stats()
            context_usage = session_stats.get("contextUsage") if isinstance(session_stats, dict) else None
            if isinstance(context_usage, dict):
                context_tokens = int(context_usage.get("tokens") or 0)
                stats_window = int(context_usage.get("contextWindow") or 0)
                if stats_window > 0:
                    context_window = stats_window
        except Exception:
            session_stats = {}
            context_tokens = 0

        return {
            "accepted": accepted,
            "text": final_text,
            "reasoning": reasoning,
            "activity": activity,
            "events": event_log,
            "stderr": stderr,
            "assistant_message": final_message,
            "usage": usage if isinstance(usage, dict) else {},
            "context_tokens": context_tokens,
            "context_window": int(context_window or 0),
            "session_stats": session_stats,
            "state": state,
            "pi_auto_compaction_disabled": self.auto_compaction_disabled,
            "pi_auto_compaction_warning": self.auto_compaction_warning,
        }

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send({"type": "abort"})
            except Exception:
                pass
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()


def _prepare_workflow_request_context(workflow: Any) -> tuple[dict[str, Any], str, Path | None]:
    """Create a compact workflow digest and an on-demand local JSON file.

    The full graph is intentionally not injected into Pi's prompt. Pi receives a bounded
    digest and a temporary file path it can read only if graph-level details are needed.
    """
    if workflow in (None, "", {}):
        return {}, "", None
    try:
        data = load_json(workflow, default={}) if isinstance(workflow, str) else workflow
    except Exception:
        return {}, "", None
    if not isinstance(data, dict) or not data:
        return {}, "", None

    # Import locally so ordinary Pi runtime startup does not pull workflow intelligence or
    # any integration adapter into memory before a workflow-aware request actually arrives.
    from .workflow import analyze_workflow

    report = analyze_workflow(data).to_dict()
    digest = {
        "format": report.get("format"),
        "node_count": report.get("node_count"),
        "link_count": report.get("link_count"),
        "node_types": report.get("node_types", {}),
        "missing_node_types": report.get("missing_node_types", [])[:50],
        "input_files": report.get("input_files", [])[:80],
        "model_candidates": report.get("model_candidates", [])[:80],
        "issues": report.get("issues", [])[:40],
        "integrations": report.get("integrations", {}),
    }
    digest_text = json.dumps(digest, ensure_ascii=False, indent=2)[:20000]

    context_dir = get_comfy_user_directory() / "pi-agent" / "request-context"
    context_dir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    token = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    path = context_dir / f"workflow-{token}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data, digest_text, path


def run_pi_prompt(
    request: str,
    provider: str = "",
    model: str = "",
    project_dir: str = "",
    executable: str = "",
    timeout: int = 180,
    workflow: Any = None,
) -> dict[str, Any]:
    status = discover_pi(executable)
    if not status.available or not status.executable:
        return {"ok": False, "runtime": status.to_dict(), "text": "", "error": status.message}
    client = PiRpcClient(status.executable, project_dir=project_dir, provider=provider, model=model, timeout=timeout)
    workflow_context_path: Path | None = None
    try:
        workflow_data, workflow_digest, workflow_context_path = _prepare_workflow_request_context(workflow)
        routed = build_dynamic_integration_context(workflow=workflow_data, message=request)
        guidance = build_request_guidance(request, workflow=workflow_data)
        integration_context = str(routed.get("context") or "")
        context_parts: list[str] = [
            guidance["core_contract"],
            guidance["task_envelope"],
        ]
        skill_context = str(guidance.get("skill_context") or "")
        if skill_context:
            context_parts.append(
                "ComfyUI-Pi dynamically selected task procedures. Follow them for this job; "
                "they were loaded because the current request matched them.\n\n" + skill_context
            )
        if integration_context:
            context_parts.append(
                "ComfyUI-Pi dynamically loaded integration context follows. It was selected "
                "only because this request matched an integration. Use it as operating guidance "
                "while still validating live ComfyUI schemas.\n\n"
                + integration_context
            )
        if workflow_digest:
            context_parts.append(
                "A compact digest of the supplied ComfyUI workflow follows. The full workflow "
                "is deliberately not embedded in this prompt."
                "\n\n" + workflow_digest
                + (f"\n\nFull workflow JSON is available locally at: {workflow_context_path}. "
                   "Read it only if graph-level details are needed." if workflow_context_path else "")
            )
        prompt = "\n\n---\n\n".join(context_parts + ["User request:\n" + request]) if context_parts else request
        result = client.prompt(prompt)
        return {
            "ok": True,
            "runtime": status.to_dict(),
            "loaded_integrations": routed.get("loaded_integrations", []),
            "loaded_skills": guidance.get("loaded_skills", []),
            "workflow_context": bool(workflow_digest),
            **result,
        }
    except Exception as exc:
        return {"ok": False, "runtime": status.to_dict(), "text": "", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        client.close()
        if workflow_context_path is not None:
            try:
                workflow_context_path.unlink(missing_ok=True)
            except Exception:
                pass
