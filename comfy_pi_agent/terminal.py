from __future__ import annotations

import errno
import json
import os
import queue
import subprocess
import shutil
import signal
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .compat import get_comfy_user_directory
from .pi_runtime import discover_pi, _extract_message_text
from .context_handoff import ContextPressure, clamp_handoff_chars, clamp_threshold, create_handoff

try:  # POSIX only; Windows falls back to structured RPC chat unless ConPTY support is added.
    import fcntl  # type: ignore
    import pty  # type: ignore
    import termios  # type: ignore
except ImportError:  # pragma: no cover - exercised by capability tests through monkeypatching
    fcntl = None  # type: ignore
    pty = None  # type: ignore
    termios = None  # type: ignore


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE_EXTENSION = _PLUGIN_ROOT / "pi" / "terminal-bridge.ts"
_BRIDGE_CLI = Path(__file__).resolve().with_name("terminal_bridge_cli.py")
_PTY_CHILD = Path(__file__).resolve().with_name("terminal_pty_child.py")


def terminal_backend_name() -> str:
    if (
        os.name == "posix"
        and pty is not None
        and fcntl is not None
        and termios is not None
        and hasattr(termios, "TIOCSCTTY")
    ):
        return "posix-controlling-pty"
    return "unavailable"


def terminal_supported() -> bool:
    return terminal_backend_name() != "unavailable"


def terminal_session_root(session_id: str) -> Path:
    safe = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("Invalid terminal session id.")
    root = get_comfy_user_directory() / "pi-agent" / "terminal-sessions" / safe
    root.mkdir(parents=True, exist_ok=True)
    return root


def _winsize(rows: int, cols: int) -> bytes:
    return struct.pack("HHHH", max(2, int(rows)), max(10, int(cols)), 0, 0)


def build_terminal_command(
    executable: str,
    provider: str = "",
    model: str = "",
    scoped_models: str = "",
    session_dir: str = "",
    session_name: str = "ComfyUI-Pi",
    resume: bool = False,
) -> list[str]:
    """Build the actual interactive Pi CLI command used by Terminal mode.

    This intentionally does *not* use --mode rpc. Pi's own TUI handles slash commands,
    tool rendering, thinking blocks, model menus, and errors. Context/skill discovery stays
    lean: ComfyUI-Pi loads one explicit bridge extension and performs task-specific guidance
    lazily through that extension.
    """
    command = [
        str(executable),
        "--no-approve",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "-e", str(_BRIDGE_EXTENSION),
    ]
    if session_dir:
        command += ["--session-dir", str(session_dir)]
    if resume:
        command += ["--continue"]
    if session_name:
        command += ["--name", str(session_name)]
    if provider.strip():
        command += ["--provider", provider.strip()]
    if model.strip():
        command += ["--model", model.strip()]
    if scoped_models.strip():
        command += ["--models", scoped_models.strip()]
    return command


@dataclass
class TerminalStatus:
    session_id: str
    supported: bool
    backend: str
    running: bool
    pid: int | None = None
    exit_code: int | None = None
    provider: str = ""
    model: str = ""
    project_directory: str = ""
    cols: int = 100
    rows: int = 32
    started_at: float = 0.0
    message: str = ""
    input_bytes: int = 0
    output_bytes: int = 0
    last_output_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PiTerminalSession:
    def __init__(
        self,
        session_id: str,
        executable: str,
        project_directory: str,
        provider: str,
        model: str,
        scoped_models: str,
        timeout: int,
        cols: int = 100,
        rows: int = 32,
        resume: bool = False,
        env_overrides: dict[str, str] | None = None,
        workflow: Any = None,
        context_settings: dict[str, Any] | None = None,
    ) -> None:
        if not terminal_supported():
            raise RuntimeError("A native PTY terminal backend is not available on this platform. Use Chat view instead.")
        self.session_id = str(session_id)
        self.root = terminal_session_root(session_id)
        self.pi_session_dir = self.root / "pi-sessions"
        self.pi_session_dir.mkdir(parents=True, exist_ok=True)
        self.workflow_path = self.root / "active-workflow.json"
        self.bridge_state_path = self.root / "bridge-state.json"
        self.bridge_config_path = self.root / "bridge-config.json"
        self.handoff_marker_path = self.root / "pending-handoff.json"
        self.executable = str(executable)
        self.project_directory = str(project_directory or "")
        self.provider = str(provider or "")
        self.model = str(model or "")
        self.scoped_models = str(scoped_models or "")
        self.timeout = max(10, int(timeout or 180))
        self.cols = max(20, int(cols or 100))
        self.rows = max(6, int(rows or 32))
        self.started_at = time.time()
        self.output_queue: queue.Queue[bytes] = queue.Queue()
        self._ring: deque[bytes] = deque()
        self._ring_bytes = 0
        self._ring_limit = 2_000_000
        self._write_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._closed = threading.Event()
        self._reader: threading.Thread | None = None
        self._monitor: threading.Thread | None = None
        self._handoff_lock = threading.Lock()
        self._last_bridge_update = 0.0
        self.master_fd: int | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self._input_bytes = 0
        self._output_bytes = 0
        self._last_output_at = 0.0
        self._save_workflow(workflow)
        self._save_bridge_config(context_settings or {})
        self._start(resume=resume, env_overrides=env_overrides or {})

    def _save_workflow(self, workflow: Any) -> None:
        if workflow in (None, "", {}):
            try:
                self.workflow_path.unlink(missing_ok=True)
            except Exception:
                pass
            return
        try:
            self.workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def update_workflow(self, workflow: Any) -> None:
        self._save_workflow(workflow)

    def _save_bridge_config(self, settings: dict[str, Any]) -> None:
        data = {
            "session_id": self.session_id,
            "workflow_path": str(self.workflow_path),
            "project_directory": self.project_directory,
            "preemptive_handoff": bool(settings.get("preemptive_handoff", True)),
            "handoff_threshold": float(settings.get("handoff_threshold", 0.825)),
            "handoff_max_chars": int(settings.get("handoff_max_chars", 8000)),
            "project_context": str(settings.get("project_context", "")),
            "timeout": self.timeout,
        }
        self.bridge_config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_bridge_config(self, settings: dict[str, Any]) -> None:
        self._save_bridge_config(settings)

    def _start(self, resume: bool, env_overrides: dict[str, str]) -> None:
        if pty is None or fcntl is None or termios is None or not hasattr(termios, "TIOCSCTTY"):
            raise RuntimeError("A controlling-terminal PTY backend is not available on this platform.")
        command = build_terminal_command(
            self.executable,
            provider=self.provider,
            model=self.model,
            scoped_models=self.scoped_models,
            session_dir=str(self.pi_session_dir),
            session_name=f"ComfyUI-Pi {self.session_id[:8]}",
            resume=resume,
        )
        cwd = Path(self.project_directory).expanduser().resolve() if self.project_directory.strip() else get_comfy_user_directory()
        cwd.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in env_overrides.items() if k and v is not None})
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        env["COMFYUI_PI_PYTHON"] = sys.executable
        env["COMFYUI_PI_BRIDGE_MODULE"] = "comfy_pi_agent.terminal_bridge_cli"
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(_PLUGIN_ROOT) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        env["COMFYUI_PI_BRIDGE_CONFIG"] = str(self.bridge_config_path)
        env["COMFYUI_PI_BRIDGE_STATE"] = str(self.bridge_state_path)
        env["COMFYUI_PI_HANDOFF_MARKER"] = str(self.handoff_marker_path)

        # A plain Popen(start_new_session=True) with a pre-opened PTY slave only gives
        # Pi TTY file descriptors; it does not make that PTY Pi's controlling terminal.
        # Launch a tiny single-threaded helper first. The helper calls setsid/TIOCSCTTY
        # safely, then execs Pi in-place so the PID/process group remains stable.
        master_fd, slave_fd = pty.openpty()
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, _winsize(self.rows, self.cols))
        helper_command = [sys.executable, str(_PTY_CHILD), "--cwd", str(cwd), "--", *command]
        try:
            process = subprocess.Popen(
                helper_command,
                cwd=str(cwd),
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        self.master_fd = master_fd
        self.process = process
        try:
            os.kill(process.pid, signal.SIGWINCH)
        except Exception:
            pass
        self._reader = threading.Thread(target=self._reader_loop, daemon=True, name=f"comfy-pi-terminal-{self.session_id[:8]}")
        self._reader.start()
        self._monitor = threading.Thread(target=self._monitor_loop, daemon=True, name=f"comfy-pi-handoff-{self.session_id[:8]}")
        self._monitor.start()

    def _append_ring(self, data: bytes) -> None:
        self._ring.append(data)
        self._ring_bytes += len(data)
        while self._ring and self._ring_bytes > self._ring_limit:
            removed = self._ring.popleft()
            self._ring_bytes -= len(removed)

    def _reader_loop(self) -> None:
        fd = self.master_fd
        if fd is None:
            return
        while not self._closed.is_set():
            try:
                data = os.read(fd, 65536)
                if not data:
                    break
            except OSError as exc:
                if exc.errno in {errno.EIO, errno.EBADF}:
                    break
                time.sleep(0.02)
                continue
            # Ring-buffer update and live-queue publication are one atomic handoff.
            # WebSocket attach takes the same lock while snapshotting/draining, so output
            # produced at the reconnect boundary is never silently discarded.
            with self._state_lock:
                self._output_bytes += len(data)
                self._last_output_at = time.time()
                self._append_ring(data)
                self.output_queue.put(data)
        self._closed.set()

    def snapshot(self) -> bytes:
        with self._state_lock:
            return b"".join(self._ring)

    def attach_snapshot(self) -> bytes:
        """Atomically snapshot terminal scrollback and synchronize the live queue.

        The WebSocket client renders the snapshot first, then consumes only output that
        arrives after this method releases the lock. This avoids both duplicate scrollback
        and the reconnect race where bytes could previously be drained after the snapshot
        without ever being sent to the browser.
        """
        with self._state_lock:
            snapshot = b"".join(self._ring)
            while True:
                try:
                    self.output_queue.get_nowait()
                except queue.Empty:
                    break
            return snapshot

    def read_output(self, timeout: float = 0.25) -> bytes:
        try:
            return self.output_queue.get(timeout=max(0.01, float(timeout)))
        except queue.Empty:
            return b""

    def drain_output_queue(self) -> None:
        while True:
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break

    def write(self, data: str | bytes) -> None:
        fd = self.master_fd
        if fd is None or self.process is None or self.process.poll() is not None:
            raise RuntimeError("Pi terminal is not running.")
        payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        if not payload:
            return
        with self._write_lock:
            written = os.write(fd, payload)
            self._input_bytes += max(0, int(written))

    def resize(self, cols: int, rows: int) -> None:
        self.cols = max(20, int(cols or self.cols))
        self.rows = max(6, int(rows or self.rows))
        fd = self.master_fd
        if fd is None or fcntl is None or termios is None:
            return
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, _winsize(self.rows, self.cols))
            if self.process and self.process.poll() is None:
                os.killpg(os.getpgid(self.process.pid), signal.SIGWINCH)
        except Exception:
            pass


    def _read_bridge_config(self) -> dict[str, Any]:
        try:
            data = json.loads(self.bridge_config_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _read_pi_visible_messages(self, session_file: str) -> list[dict[str, str]]:
        """Read only user/assistant visible text from Pi's JSONL session.

        Tool payloads, reasoning blocks, and binary/large content are intentionally omitted
        from the handoff source. Large artifacts remain referenced by path.
        """
        path = Path(str(session_file or "")).expanduser()
        if not path.is_file():
            return []
        messages: list[dict[str, str]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    try:
                        item = json.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(item, dict) or item.get("type") != "message":
                        continue
                    message = item.get("message")
                    if not isinstance(message, dict):
                        continue
                    role = str(message.get("role") or "")
                    if role not in {"user", "assistant"}:
                        continue
                    text = _extract_message_text(message).strip()
                    if text:
                        messages.append({"role": role, "content": text})
        except Exception:
            return []
        return messages

    def _workflow_digest(self) -> str:
        if not self.workflow_path.is_file():
            return ""
        try:
            workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        if not isinstance(workflow, dict):
            return ""
        nodes = workflow.get("nodes")
        nodes = nodes if isinstance(nodes, list) else []
        counts: dict[str, int] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("type") or node.get("class_type") or "unknown")
            counts[node_type] = counts.get(node_type, 0) + 1
        links = workflow.get("links")
        link_count = len(links) if isinstance(links, list) else 0
        return json.dumps({"node_count": len(nodes), "link_count": link_count, "node_types": counts}, ensure_ascii=False)[:6000]

    def _emit_host_notice(self, text: str) -> None:
        payload = ("\r\n\x1b[36m[ComfyUI-Pi] " + str(text).strip() + "\x1b[0m\r\n").encode("utf-8", errors="replace")
        with self._state_lock:
            self._append_ring(payload)
        self.output_queue.put(payload)

    def _create_preemptive_handoff(self, bridge: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
        if not bool(config.get("preemptive_handoff", True)):
            return None
        try:
            percent = float(bridge.get("context_percent"))
        except (TypeError, ValueError):
            return None
        # Pi reports percent as 0..100. Accept ratio form defensively too.
        ratio = percent / 100.0 if percent > 1.0 else percent
        threshold = clamp_threshold(config.get("handoff_threshold", 0.825))
        if ratio < threshold:
            return None
        try:
            tokens = max(0, int(bridge.get("context_tokens") or 0))
            window = max(0, int(bridge.get("context_window") or 0))
        except (TypeError, ValueError):
            return None
        if not tokens or not window:
            return None
        pressure = ContextPressure(tokens, window, ratio, threshold, True, source="pi_terminal_extension")
        visible = self._read_pi_visible_messages(str(bridge.get("session_file") or ""))
        document = {
            "session_id": self.session_id,
            "title": f"Pi terminal {self.session_id[:8]}",
            "project_directory": self.project_directory,
            "provider": self.provider,
            "model": self.model,
            "messages": visible,
        }
        metadata = create_handoff(
            self.session_id,
            document,
            pressure,
            project_context=str(config.get("project_context") or ""),
            workflow_summary=self._workflow_digest(),
            workflow_context_path=str(self.workflow_path) if self.workflow_path.is_file() else "",
            routed_context=None,
            max_chars=clamp_handoff_chars(config.get("handoff_max_chars", 8000)),
            summarizer=None,
        )
        marker = {
            "created_at": time.time(),
            "handoff_path": str(metadata.get("path") or ""),
            "handoff_index": metadata.get("handoff_index"),
            "context_pressure": pressure.to_dict(),
        }
        self.handoff_marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        # Clear the old high-water mark before issuing /new so the monitor cannot loop on
        # the same completed turn while Pi redraws the TUI.
        reset_state = dict(bridge)
        reset_state.update({
            "updated_at": time.time(),
            "context_tokens": 0,
            "context_percent": 0.0,
            "preemptive_handoff": marker,
        })
        self.bridge_state_path.write_text(json.dumps(reset_state, ensure_ascii=False, indent=2), encoding="utf-8")
        self._emit_host_notice(
            f"Context reached {ratio * 100:.1f}% (threshold {threshold * 100:.1f}%). "
            f"Saved handoff-{int(metadata.get('handoff_index') or 0):04d} and starting a fresh Pi session."
        )
        # Native Pi handles /new itself. Keeping the same PTY preserves the browser terminal
        # while replacing the LLM context. The bridge injects the bounded handoff exactly
        # once on the next real user prompt.
        self.write("/new\r")
        return metadata

    def _monitor_loop(self) -> None:
        while not self._closed.wait(0.5):
            if not self.bridge_state_path.is_file():
                continue
            try:
                bridge = json.loads(self.bridge_state_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(bridge, dict):
                continue
            try:
                updated = float(bridge.get("updated_at") or 0.0)
            except (TypeError, ValueError):
                updated = 0.0
            if updated <= self._last_bridge_update:
                continue
            self._last_bridge_update = updated
            config = self._read_bridge_config()
            if not self._handoff_lock.acquire(blocking=False):
                continue
            try:
                self._create_preemptive_handoff(bridge, config)
            except Exception as exc:
                self._emit_host_notice(f"Preemptive handoff failed safely: {type(exc).__name__}: {exc}")
            finally:
                self._handoff_lock.release()

    def status(self) -> TerminalStatus:
        process = self.process
        code = process.poll() if process else None
        running = process is not None and code is None and not self._closed.is_set()
        if running and self._output_bytes == 0 and time.time() - self.started_at > 3.0:
            message = "Pi process is running, but the PTY has not produced terminal output yet."
        else:
            message = "Pi interactive terminal is running." if running else "Pi interactive terminal is stopped."
        return TerminalStatus(
            session_id=self.session_id,
            supported=True,
            backend=terminal_backend_name(),
            running=running,
            pid=process.pid if process else None,
            exit_code=code,
            provider=self.provider,
            model=self.model,
            project_directory=self.project_directory,
            cols=self.cols,
            rows=self.rows,
            started_at=self.started_at,
            message=message,
            input_bytes=self._input_bytes,
            output_bytes=self._output_bytes,
            last_output_at=self._last_output_at,
        )

    def stop(self, graceful: bool = True) -> None:
        process = self.process
        if process is None:
            return
        if process.poll() is None and graceful:
            try:
                self.write("/quit\r")
                process.wait(timeout=2.0)
            except Exception:
                pass
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=2.0)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._closed.set()
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None


class PiTerminalManager:
    def __init__(self) -> None:
        self._sessions: dict[str, PiTerminalSession] = {}
        self._lock = threading.RLock()

    def capability(self) -> dict[str, Any]:
        return {
            "supported": terminal_supported(),
            "backend": terminal_backend_name(),
            "message": (
                "Real Pi interactive terminal is available."
                if terminal_supported()
                else "Native PTY support is unavailable; use structured Chat view."
            ),
        }

    def get(self, session_id: str) -> PiTerminalSession | None:
        with self._lock:
            return self._sessions.get(str(session_id))

    def start(
        self,
        session_id: str,
        executable: str = "",
        project_directory: str = "",
        provider: str = "",
        model: str = "",
        scoped_models: str = "",
        timeout: int = 180,
        cols: int = 100,
        rows: int = 32,
        resume: bool = False,
        env_overrides: dict[str, str] | None = None,
        workflow: Any = None,
        context_settings: dict[str, Any] | None = None,
    ) -> PiTerminalSession:
        status = discover_pi(executable)
        if not status.available or not status.executable:
            raise RuntimeError(status.message)
        with self._lock:
            existing = self._sessions.get(str(session_id))
            if existing and existing.status().running:
                existing.update_workflow(workflow)
                existing.update_bridge_config(context_settings or {})
                existing.resize(cols, rows)
                return existing
            if existing:
                existing.stop(graceful=False)
            session = PiTerminalSession(
                session_id=str(session_id),
                executable=str(status.executable),
                project_directory=project_directory,
                provider=provider,
                model=model,
                scoped_models=scoped_models,
                timeout=timeout,
                cols=cols,
                rows=rows,
                resume=resume,
                env_overrides=env_overrides,
                workflow=workflow,
                context_settings=context_settings,
            )
            self._sessions[str(session_id)] = session
            return session

    def restart(
        self,
        session_id: str,
        provider: str,
        model: str,
        scoped_models: str = "",
        timeout: int = 180,
        env_overrides: dict[str, str] | None = None,
        workflow: Any = None,
        context_settings: dict[str, Any] | None = None,
    ) -> PiTerminalSession:
        with self._lock:
            existing = self._sessions.get(str(session_id))
            if not existing:
                raise RuntimeError("Pi terminal has not been started yet.")
            executable = existing.executable
            project_directory = existing.project_directory
            cols, rows = existing.cols, existing.rows
            existing.stop(graceful=True)
            session = PiTerminalSession(
                session_id=str(session_id),
                executable=executable,
                project_directory=project_directory,
                provider=provider,
                model=model,
                scoped_models=scoped_models,
                timeout=timeout,
                cols=cols,
                rows=rows,
                resume=True,
                env_overrides=env_overrides,
                workflow=workflow,
                context_settings=context_settings,
            )
            self._sessions[str(session_id)] = session
            return session

    def stop(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(str(session_id), None)
        if not session:
            return False
        session.stop(graceful=True)
        return True

    def status(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        if not session:
            cap = self.capability()
            return {
                "session_id": str(session_id),
                "supported": cap["supported"],
                "backend": cap["backend"],
                "running": False,
                "message": cap["message"],
            }
        data = session.status().to_dict()
        if session.bridge_state_path.exists():
            try:
                bridge = json.loads(session.bridge_state_path.read_text(encoding="utf-8"))
                if isinstance(bridge, dict):
                    data["bridge"] = bridge
            except Exception:
                pass
        return data


TERMINAL_MANAGER = PiTerminalManager()
