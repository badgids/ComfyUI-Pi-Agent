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
        self.assertIn("Pi Agent Chat", js)
        self.assertIn("user-select:text", js)
        self.assertIn("navigator.clipboard", js)
        self.assertIn("Shift+Enter", js)
        self.assertIn("/pi-agent/chat/send", js)
        self.assertIn("Include the current ComfyUI workflow", js)
        self.assertIn("Preemptive context handoff and reset", js)
        self.assertIn("handoff_threshold_percent", js)
        self.assertIn('max="95"', js)
        self.assertIn("Context --", js)


if __name__ == "__main__":
    unittest.main()
