import json
import os
import queue
import tempfile
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.pi_runtime import PiRpcClient
from comfy_pi_agent.terminal import PiTerminalSession, build_terminal_command
from comfy_pi_agent.terminal_bridge_cli import build_terminal_guidance

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

    def test_terminal_bridge_intercepts_threshold_compaction_and_injects_handoff(self):
        text = (ROOT / "pi" / "terminal-bridge.ts").read_text(encoding="utf-8")
        self.assertIn('pi.on("session_before_compact"', text)
        self.assertIn('event.reason === "threshold"', text)
        self.assertIn("return { cancel: true }", text)
        self.assertIn("COMFYUI-PI CONTINUITY HANDOFF", text)
        self.assertIn('pi.on("before_agent_start"', text)
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

    def test_terminal_preemptive_handoff_uses_pi_session_and_native_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("comfy_pi_agent.terminal.terminal_supported", return_value=True), \
                 patch("comfy_pi_agent.terminal.terminal_session_root", return_value=root / "terminal"), \
                 patch("comfy_pi_agent.context_handoff.get_comfy_user_directory", return_value=root), \
                 patch.object(PiTerminalSession, "_start", return_value=None):
                session = PiTerminalSession(
                    session_id="abc123", executable="pi", project_directory="", provider="local",
                    model="model", scoped_models="", timeout=123,
                    context_settings={"preemptive_handoff": True, "handoff_threshold": 0.825, "handoff_max_chars": 8000},
                )
                pi_session = root / "session.jsonl"
                pi_session.write_text(
                    json.dumps({"type": "session", "id": "s", "cwd": str(root)}) + "\n" +
                    json.dumps({"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "Keep working on the workflow"}]}}) + "\n" +
                    json.dumps({"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Current work is in progress"}]}}) + "\n",
                    encoding="utf-8",
                )
                writes = []
                session.write = lambda value: writes.append(value)
                metadata = session._create_preemptive_handoff(
                    {"context_percent": 83.0, "context_tokens": 83000, "context_window": 100000, "session_file": str(pi_session)},
                    {"preemptive_handoff": True, "handoff_threshold": 0.825, "handoff_max_chars": 8000},
                )
                self.assertIsNotNone(metadata)
                self.assertTrue(Path(metadata["path"]).is_file())
                self.assertTrue(session.handoff_marker_path.is_file())
                self.assertEqual(writes, ["/new\r"])

    def test_frontend_terminal_is_default_and_chat_reasoning_tools_default_visible(self):
        js = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn('view: "terminal"', js)
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
        self.assertNotIn('id="pi-agent-terminal-host" class="pi-agent-terminal-host" tabindex="0"', js)
        self.assertIn('id: "PiAgent.UI.Placement"', js)
        self.assertIn('options: ["Left sidebar", "Bottom panel"]', js)
        self.assertIn('bottomPanelTabs:', js)
        self.assertIn('targetPanel: "terminal"', js)
        self.assertIn('initializeSidebar(el, "bottom")', js)


if __name__ == "__main__":
    unittest.main()
