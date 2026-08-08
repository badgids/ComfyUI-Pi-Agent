import json
import os
import queue
import tempfile
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import comfy_pi_agent.routes as pi_routes
from comfy_pi_agent.pi_runtime import PiRpcClient
from comfy_pi_agent.terminal import PiTerminalSession, build_terminal_command
from comfy_pi_agent.terminal_bridge_cli import build_terminal_guidance, create_terminal_handoff

ROOT = Path(__file__).resolve().parents[1]


class FakeProcess:
    def poll(self):
        return None


class RpcRecoveryTests(unittest.TestCase):
    def make_client(self):
        client = PiRpcClient.__new__(PiRpcClient)
        client.timeout = 2
        client.events = queue.Queue()
        client.stderr_lines = queue.Queue()
        client.stderr_history = []
        client.process = FakeProcess()
        client.auto_compaction_disabled = True
        client.auto_compaction_warning = ""
        client.send = lambda payload: None
        client.get_state = lambda: {"model": {"contextWindow": 100000}}
        client.get_session_stats = lambda: {"contextUsage": {"tokens": 100, "contextWindow": 100000}}
        client.get_messages = lambda: []
        return client

    def test_rpc_uses_authoritative_last_assistant_text_when_events_have_no_text(self):
        client = self.make_client()
        client.events.put({"type": "response", "id": "comfy-1", "success": True})
        client.events.put({"type": "agent_settled"})
        client.get_last_assistant_text = lambda: "Recovered final answer"
        # Make the generated request id deterministic enough for our queued response.
        with patch("comfy_pi_agent.pi_runtime.time.time", return_value=0.001):
            result = client.prompt("hello")
        self.assertEqual(result["text"], "Recovered final answer")

    def test_rpc_collects_reasoning_and_tool_activity(self):
        client = self.make_client()
        client.events.put({"type": "response", "id": "comfy-1", "success": True})
        client.events.put({"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "considering"}})
        client.events.put({"type": "tool_execution_start", "toolCallId": "1", "toolName": "read"})
        client.events.put({"type": "tool_execution_end", "toolCallId": "1", "toolName": "read", "result": {"ok": True}, "isError": False})
        client.events.put({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}], "usage": {}}})
        client.events.put({"type": "agent_settled"})
        client.get_last_assistant_text = lambda: ""
        with patch("comfy_pi_agent.pi_runtime.time.time", return_value=0.001):
            result = client.prompt("hello")
        self.assertEqual(result["text"], "Done")
        self.assertEqual(result["reasoning"], "considering")
        self.assertEqual([item["type"] for item in result["activity"]], ["tool_execution_start", "tool_execution_end"])


class TerminalArchitectureTests(unittest.TestCase):
    def test_terminal_websocket_json_codec_is_available(self):
        payload = {"type": "output", "data": "Pi ready"}
        encoded = pi_routes.json.dumps(payload)
        self.assertEqual(pi_routes.json.loads(encoded), payload)

    def test_terminal_command_is_real_interactive_pi_not_rpc(self):
        command = build_terminal_command(
            "pi", provider="llama.cpp", model="test-model", scoped_models="llama.cpp/*",
            session_dir="/tmp/comfy-pi-session", resume=True,
        )
        self.assertNotIn("rpc", command)
        self.assertNotIn("--mode", command)
        self.assertIn("--no-context-files", command)
        self.assertIn("--no-extensions", command)
        self.assertIn("--no-skills", command)
        self.assertIn("-e", command)
        bridge = command[command.index("-e") + 1]
        self.assertTrue(bridge.endswith("pi/terminal-bridge.ts"))
        self.assertIn("--continue", command)
        self.assertEqual(command[command.index("--provider") + 1], "llama.cpp")
        self.assertEqual(command[command.index("--model") + 1], "test-model")

    def test_terminal_saved_session_recovery_architecture_is_present(self):
        terminal_source = (ROOT / "comfy_pi_agent" / "terminal.py").read_text(encoding="utf-8")
        self.assertIn("def _has_persisted_pi_session", terminal_source)
        self.assertIn("self._start(resume=True", terminal_source)
        self.assertIn("Automatically reopening and resuming the saved Pi session", terminal_source)
        self.assertIn("resume_saved = bool(resume or _has_persisted_pi_session(session_id))", terminal_source)
        self.assertIn("def _record_terminal_title", terminal_source)

        route_source = (ROOT / "comfy_pi_agent" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("if not status.running and status.recovering", route_source)

        frontend_source = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn("terminalRecoveryAttempts", frontend_source)
        self.assertIn("resumeSaved = Boolean(status.resumable)", frontend_source)
        self.assertIn("option.textContent = String(status.title)", frontend_source)


    @unittest.skipUnless(os.name == "posix", "requires POSIX controlling PTY")
    def test_real_terminal_child_has_controlling_tty_and_accepts_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = (
                "import os,sys; "
                "print('TTY=%s CTRL=%s' % (os.isatty(0) and os.isatty(1), os.tcgetpgrp(0)==os.getpgrp()), flush=True); "
                "line=sys.stdin.readline(); print('ECHO:'+line.strip(), flush=True)"
            )
            with patch("comfy_pi_agent.terminal.terminal_session_root", return_value=root / "terminal"), \
                 patch("comfy_pi_agent.terminal.build_terminal_command", return_value=[sys.executable, "-c", code]):
                session = PiTerminalSession(
                    session_id="ptytest", executable=sys.executable, project_directory=str(root),
                    provider="", model="", scoped_models="", timeout=30,
                )
                try:
                    output = b""
                    deadline = time.time() + 4
                    while b"CTRL=True" not in output and time.time() < deadline:
                        output += session.read_output(0.1)
                    self.assertIn(b"TTY=True CTRL=True", output)
                    session.write("hello from browser\r")
                    deadline = time.time() + 4
                    while b"ECHO:hello from browser" not in output and time.time() < deadline:
                        output += session.read_output(0.1)
                    self.assertIn(b"ECHO:hello from browser", output)
                    status = session.status()
                    self.assertGreater(status.output_bytes, 0)
                    self.assertGreater(status.input_bytes, 0)
                finally:
                    session.stop(graceful=False)

    def test_terminal_guidance_stays_lazy(self):
        plain = build_terminal_guidance("Say hello")
        self.assertNotIn("MiniMax H3 Director", plain)
        matched = build_terminal_guidance("Create a MiniMax H3 Turbo workflow")
        self.assertIn("MiniMax", matched)
        self.assertLess(len(matched), 24001)

    def test_terminal_bridge_keeps_pi_native_in_place_compaction(self):
        text = (ROOT / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn('pi.on("session_before_compact"', text)
        self.assertIn('pi.on("session_compact"', text)
        self.assertIn('pi.on("agent_end"', text)
        self.assertIn('pi.on("agent_settled"', text)
        self.assertIn('await maybeRequestEarlyCompaction(ctx, "agent-end")', text)
        self.assertIn('await maybeRequestEarlyCompaction(ctx, "agent-settled")', text)
        self.assertIn("appendCustomMessageEntry", text)
        self.assertIn("branchContainsEntry", text)
        self.assertIn("pendingHandoffText", text)
        self.assertIn("firstKeptEntryId", text)
        self.assertIn("ctx.compact({", text)
        self.assertIn("--create-handoff", text)
        self.assertNotIn("return { cancel: true }", text)
        self.assertNotIn("if (!usage?.tokens || !usage?.contextWindow", text)
        self.assertIn('return undefined;', text)
        self.assertIn("LEGACY COMFYUI-PI CONTINUITY HANDOFF", text)
        self.assertIn("--message-file", text)
        self.assertIn("ctx.getContextUsage", text)


    def test_terminal_attach_snapshot_does_not_drop_reconnect_boundary_output(self):
        import threading
        from collections import deque
        session = PiTerminalSession.__new__(PiTerminalSession)
        session._ring = deque([b"old\r\n"])
        session._ring_bytes = len(b"old\r\n")
        session._ring_limit = 1024
        session._state_lock = threading.RLock()
        session.output_queue = queue.Queue()
        session.output_queue.put(b"old\r\n")
        snapshot = session.attach_snapshot()
        self.assertEqual(snapshot, b"old\r\n")
        self.assertTrue(session.output_queue.empty())
        with session._state_lock:
            session._append_ring(b"new\r\n")
            session.output_queue.put(b"new\r\n")
        self.assertEqual(session.read_output(0.01), b"new\r\n")

    def test_terminal_bridge_cli_accepts_message_file_for_large_pastes(self):
        bridge = (ROOT / "comfy_pi_agent" / "terminal_bridge_cli.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--message-file"', bridge)
        self.assertIn('read_text(encoding="utf-8")', bridge)

    def test_terminal_compaction_checkpoint_never_starts_a_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / "workflow.json"
            workflow.write_text(
                json.dumps({"nodes": [{"type": "TestNode"}], "links": []}),
                encoding="utf-8",
            )
            config = root / "bridge-config.json"
            config.write_text(
                json.dumps({
                    "session_id": "abc123",
                    "workflow_path": str(workflow),
                    "project_directory": str(root),
                    "provider": "llama.cpp",
                    "model": "model",
                    "preemptive_handoff": True,
                    "handoff_threshold": 0.825,
                    "handoff_max_chars": 8000,
                    "project_context": "Preserve the approved workflow edits.",
                }),
                encoding="utf-8",
            )
            pi_session = root / "session.jsonl"
            pi_session.write_text(
                json.dumps({"type": "session", "id": "s", "cwd": str(root)}) + "\n" +
                json.dumps({"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "Keep working on the workflow"}]}}) + "\n" +
                json.dumps({"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Current work is in progress"}]}}) + "\n",
                encoding="utf-8",
            )
            with patch("comfy_pi_agent.context_handoff.get_comfy_user_directory", return_value=root):
                metadata = create_terminal_handoff(
                    str(config), str(pi_session), 83000, 100000, "threshold"
                )
            self.assertTrue(Path(metadata["path"]).is_file())
            self.assertEqual(metadata["compaction_reason"], "threshold")
            handoff_text = Path(metadata["path"]).read_text(encoding="utf-8")
            self.assertIn("Keep working on the workflow", handoff_text)

        terminal_source = (ROOT / "comfy_pi_agent" / "terminal.py").read_text(encoding="utf-8")
        start_source = terminal_source[
            terminal_source.index("    def _start("):
            terminal_source.index("    def _append_ring(")
        ]
        self.assertNotIn("target=self._monitor_loop", start_source)
        self.assertNotIn('self.write("/new\\r")', terminal_source)

    def test_terminal_start_route_reattaches_before_llama_readiness_work(self):
        routes = (ROOT / "comfy_pi_agent" / "routes.py").read_text(encoding="utf-8")
        start = routes[
            routes.index('async def pi_agent_terminal_start'):
            routes.index('async def pi_agent_terminal_restart')
        ]
        self.assertIn("existing = TERMINAL_MANAGER.get(session_id)", start)
        self.assertIn('"reattached": True', start)
        self.assertLess(
            start.index("existing = TERMINAL_MANAGER.get(session_id)"),
            start.index("CHAT_MANAGER._ensure_llama_router_model"),
        )

    def test_frontend_terminal_is_default_and_chat_reasoning_tools_default_visible(self):
        js = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn('view: sessionStorage.getItem("ComfyUIPi.ActiveView") === "chat" ? "chat" : "terminal"', js)
        self.assertIn('>Terminal</button>', js)
        self.assertIn('>Chat</button>', js)
        self.assertIn('id="pi-agent-show-reasoning" type="checkbox" checked', js)
        self.assertIn('id="pi-agent-show-tools" type="checkbox" checked', js)
        self.assertIn("/pi-agent/terminal/ws/", js)
        provider_pos = js.index('for="pi-agent-provider">Provider')
        model_pos = js.index('for="pi-agent-model">Model')
        self.assertLess(provider_pos, model_pos)
        self.assertTrue((ROOT / "web" / "vendor" / "xterm.js").is_file())
        self.assertTrue((ROOT / "web" / "vendor" / "XTERM_LICENSE.txt").is_file())
        self.assertIn('typeof term.onData === "function"', js)
        self.assertIn('addEventListener("pointerdown"', js)
        self.assertIn('sessionStorage.getItem("ComfyUIPi.ActiveSession")', js)
        self.assertIn('sessionStorage.setItem("ComfyUIPi.ActiveView", target)', js)
        self.assertIn('event.clipboardData?.getData("text/plain")', js)
        self.assertIn('copyTerminalSelection', js)
        self.assertIn('term._comfyPiClipboardCleanup', js)
        load_session_source = js[js.index("async function loadSession"):js.index("async function refreshSessions")]
        self.assertNotIn("applyProviderSelection(", load_session_source)
        self.assertIn('CHAT_STATE.terminalSupported ? CHAT_STATE.view : "chat"', js)
        self.assertIn("function attachTerminalHost(term, ui)", js)
        self.assertIn("ui.terminalHost.appendChild(term.element)", js)
        self.assertIn('CHAT_STATE.terminalSocket?.readyState === WebSocket.OPEN', js)
        self.assertIn("status.running || status.recovering", js)
        self.assertIn('"Reconnecting to existing Pi terminal…"', js)
        self.assertIn("resumeSaved = Boolean(status.resumable)", js)
        self.assertIn('if (CHAT_STATE.terminal && CHAT_STATE.view === "terminal")', js)
        self.assertIn("destroy: () => detachPiInterface()", js)
        detach_source = js[
            js.index("function detachPiInterface"):
            js.index("function attachTerminalHost")
        ]
        self.assertNotIn("closeTerminalSocket()", detach_source)
        self.assertNotIn("term.dispose", detach_source)
        self.assertNotIn('id="pi-agent-terminal-host" class="pi-agent-terminal-host" tabindex="0"', js)
        self.assertIn('id: "PiAgent.UI.Placement"', js)
        self.assertIn('options: ["Left sidebar", "Bottom panel"]', js)
        self.assertIn('bottomPanelTabs:', js)
        self.assertIn('targetPanel: "terminal"', js)
        self.assertIn('initializeSidebar(el, "bottom")', js)


if __name__ == "__main__":
    unittest.main()
