import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.chat import ChatRuntimeManager, ChatSessionStore


class ChatSessionStoreTests(unittest.TestCase):
    def test_create_append_list_clear_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("comfy_pi_agent.chat._session_root", return_value=root):
                store = ChatSessionStore()
                session = store.create(project_directory="/tmp/project", provider="provider", model="model")
                sid = session["session_id"]
                self.assertTrue((root / f"{sid}.json").is_file())

                session = store.append(sid, "user", "Please explain this workflow.")
                self.assertEqual(session["title"], "Please explain this workflow.")
                session = store.append(sid, "assistant", "Here is the explanation.")
                self.assertEqual(len(session["messages"]), 2)

                listing = store.list()
                self.assertEqual(listing[0]["session_id"], sid)
                self.assertEqual(listing[0]["message_count"], 2)

                renamed = store.rename(sid, "Workflow repair")
                self.assertEqual(renamed["title"], "Workflow repair")

                imported = store.import_document(store.load(sid))
                self.assertNotEqual(imported["session_id"], sid)
                self.assertEqual(imported["title"], "Workflow repair")
                self.assertEqual(len(imported["messages"]), 2)
                self.assertEqual(imported["messages"][0]["role"], "user")

                cleared = store.clear(sid)
                self.assertEqual(cleared["messages"], [])
                self.assertEqual(cleared["title"], "New chat")
                self.assertTrue(store.delete(sid))
                self.assertFalse(store.delete(sid))

    def test_agent_message_uses_compact_workflow_context(self):
        message = ChatRuntimeManager.build_agent_message(
            "Make this easier to understand.",
            workflow={"nodes": [{"id": 1, "type": "Example", "widgets_values": ["VERY_LARGE_PAYLOAD_MARKER"]}], "links": []},
            project_context="Scene 4 is the workshop scene.",
            workflow_context_path="/tmp/comfyui-pi-active-workflow.json",
        )
        self.assertIn("ComfyUI Pi Agent sidebar chat", message)
        self.assertIn("Scene 4 is the workshop scene", message)
        self.assertIn('"Example": 1', message)
        self.assertIn("Full current workflow JSON is available locally", message)
        self.assertIn("comfyui-pi-active-workflow.json", message)
        self.assertNotIn("VERY_LARGE_PAYLOAD_MARKER", message)
        self.assertIn("Make this easier to understand", message)

    def test_scope_signature_changes_with_integration_context(self):
        none = ChatRuntimeManager._scope_signature({"loaded_integrations": [], "context": ""}, "", "")
        wdc = ChatRuntimeManager._scope_signature({"loaded_integrations": [{"id": "whatdreamscost-comfyui"}], "context": "LTX"}, "", "")
        mini = ChatRuntimeManager._scope_signature({"loaded_integrations": [{"id": "minimax-h3-director"}], "context": "H3"}, "", "")
        self.assertNotEqual(none, wdc)
        self.assertNotEqual(wdc, mini)


    def test_scope_signature_changes_with_selected_task_procedure(self):
        base = {"loaded_integrations": [], "context": ""}
        workflow = {"loaded_skills": [{"name": "workflow-intelligence"}]}
        story = {"loaded_skills": [{"name": "narrative-project"}]}
        none = ChatRuntimeManager._scope_signature(base, "", "", guidance={})
        one = ChatRuntimeManager._scope_signature(base, "", "", guidance=workflow)
        two = ChatRuntimeManager._scope_signature(base, "", "", guidance=story)
        self.assertNotEqual(none, one)
        self.assertNotEqual(one, two)

    def test_clean_history_excludes_hidden_context_by_construction(self):
        history = ChatRuntimeManager._clean_history([
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
            {"role": "tool", "content": "HIDDEN_TOOL_PAYLOAD"},
        ])
        self.assertIn("Question", history)
        self.assertIn("Answer", history)
        self.assertNotIn("HIDDEN_TOOL_PAYLOAD", history)


class SidebarChatFrontendTests(unittest.TestCase):
    def test_sidebar_js_has_copy_paste_friendly_chat_ui(self):
        js = (Path(__file__).parents[1] / "web" / "pi_agent.js").read_text(encoding="utf-8")
        self.assertIn('class="pi-agent-title">Pi Agent</span>', js)
        self.assertIn("user-select:text", js)
        self.assertIn("navigator.clipboard", js)
        self.assertIn("Shift+Enter", js)
        self.assertIn("/pi-agent/chat/send", js)
        self.assertIn("Include the current ComfyUI workflow", js)
        self.assertIn("Durable context checkpoint + in-place Pi compaction", js)
        self.assertIn("handoff_threshold_percent", js)
        self.assertIn('max="95"', js)
        self.assertIn("Context --", js)

    def test_sidebar_session_management_and_terminal_layout(self):
        root = Path(__file__).parents[1]
        js = (root / "web" / "pi_agent.js").read_text(encoding="utf-8")
        routes = (root / "comfy_pi_agent" / "routes.py").read_text(encoding="utf-8")
        self.assertNotIn('id="pi-agent-copy-chat"', js)
        self.assertIn('id="pi-agent-new-chat" class="pi-agent-btn pi-agent-icon-btn"', js)
        self.assertIn('title="New session" aria-label="New session"', js)
        self.assertIn("pi pi-plus", js)
        self.assertIn('id="pi-agent-load-session"', js)
        self.assertIn('id="pi-agent-save-session"', js)
        self.assertIn('id="pi-agent-rename-session"', js)
        self.assertNotIn('id="pi-agent-clear-chat"', js)
        self.assertNotIn('aria-label="Clear session"', js)
        self.assertNotIn("🧹", js)
        self.assertIn("pi pi-trash", js)
        self.assertIn('<div id="pi-agent-terminal-tab"', js)
        self.assertIn('<div id="pi-agent-chat-tab"', js)
        self.assertNotIn("Text, reasoning, and tool activity are selectable and copyable.", js)
        self.assertIn("new Blob", js)
        self.assertIn("/pi-agent/chat/import", js)
        self.assertIn("/rename", js)
        self.assertIn('@routes.post("/pi-agent/chat/import")', routes)
        self.assertIn('/pi-agent/chat/session/{session_id}/rename', routes)
        self.assertNotIn('id="pi-agent-send"', js)
        self.assertNotIn("ui.send", js)
        self.assertIn('el.classList.add("pi-agent-interface-root")', js)
        self.assertIn(".pi-agent-interface-root { height:100%; min-height:0;", js)
        self.assertIn(".pi-agent-composer-actions[hidden] { display:none !important;", js)
        chat_pane_at = js.index('id="pi-agent-chat-pane"')
        chat_actions_at = js.index('id="pi-agent-chat-actions"')
        shared_controls_at = js.index('class="pi-agent-shared-controls"')
        self.assertLess(chat_pane_at, chat_actions_at)
        self.assertLess(chat_actions_at, shared_controls_at)
        self.assertIn(".pi-agent-terminal-pane { flex:1 1 0; min-height:0;", js)


if __name__ == "__main__":
    unittest.main()
