import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.context_handoff import (
    ContextPressure,
    calculate_context_tokens,
    clamp_threshold,
    context_pressure,
    create_handoff,
    handoff_is_sufficient,
)
from comfy_pi_agent.chat import ChatRuntimeManager, ChatSessionStore, _LiveSession


class ContextPressureTests(unittest.TestCase):
    def test_pi_usage_calculation_matches_total_tokens_preference(self):
        self.assertEqual(calculate_context_tokens({"totalTokens": 83000, "input": 1, "output": 2}), 83000)
        self.assertEqual(
            calculate_context_tokens({"input": 50000, "output": 10000, "cacheRead": 20000, "cacheWrite": 3000}),
            83000,
        )

    def test_threshold_is_clamped_to_requested_80_95_band(self):
        self.assertEqual(clamp_threshold(70), 0.80)
        self.assertEqual(clamp_threshold(90), 0.90)
        self.assertEqual(clamp_threshold(99), 0.95)
        self.assertAlmostEqual(clamp_threshold(82.5), 0.825)


    def test_weak_handoff_summary_is_rejected(self):
        self.assertFalse(handoff_is_sufficient("done"))
        self.assertFalse(handoff_is_sufficient("## Primary Objective\nX"))
        good = (
            "# Continuity Handoff\n\n## Primary Objective\nContinue the project without changing approved work.\n\n"
            "## Current State\nThe screenplay and shot list exist and the current workflow is waiting for validation.\n\n"
            "## Open Problems / Risks\nOne model path still needs verification against the installed registry.\n\n"
            "## Next Actions\nInspect the installed model registry, repair only the affected loader, then validate the workflow and record the result."
        )
        self.assertTrue(handoff_is_sufficient(good))

    def test_pressure_triggers_at_default_82_5_percent(self):
        before = context_pressure({"totalTokens": 82499}, 100000, 82.5)
        after = context_pressure({"totalTokens": 82500}, 100000, 82.5)
        self.assertFalse(before.should_handoff)
        self.assertTrue(after.should_handoff)
        self.assertAlmostEqual(after.ratio, 0.825)

    def test_prompt_result_prefers_exact_rpc_context_usage(self):
        pressure = ChatRuntimeManager._pressure_from_prompt_result(
            {
                "context_tokens": 83000,
                "context_window": 100000,
                "usage": {"totalTokens": 12000},
            },
            0.825,
        )
        self.assertEqual(pressure.context_tokens, 83000)
        self.assertTrue(pressure.should_handoff)

    def test_prompt_result_prefers_exact_rpc_context_usage(self):
        pressure = ChatRuntimeManager._pressure_from_prompt_result(
            {
                "context_tokens": 83000,
                "context_window": 100000,
                "usage": {"totalTokens": 12000},
            },
            0.825,
        )
        self.assertEqual(pressure.context_tokens, 83000)
        self.assertTrue(pressure.should_handoff)


class HandoffFileTests(unittest.TestCase):
    def test_handoff_is_bounded_and_references_workflow_instead_of_embedding_it(self):
        with tempfile.TemporaryDirectory() as td, patch(
            "comfy_pi_agent.context_handoff.get_comfy_user_directory", return_value=Path(td)
        ):
            document = {
                "session_id": "abc",
                "title": "Long project",
                "messages": [
                    {"role": "user", "content": "Continue the film project and preserve the approved character."},
                    {"role": "assistant", "content": "Completed the storyboard pass."},
                ],
            }
            pressure = ContextPressure(83000, 100000, 0.83, 0.825, True)
            metadata = create_handoff(
                "abc",
                document,
                pressure,
                project_context="Approved character bible v4.",
                workflow_summary='{"node_count": 250, "node_types": {"LTXDirector": 1}}',
                workflow_context_path="/tmp/full-workflow.json",
                max_chars=5000,
                summarizer=lambda source, budget: (
                    "# ComfyUI-Pi Continuity Handoff\n\n## Primary Objective\nContinue the film.\n\n"
                    "## Active Artifacts and Paths\nFull workflow: /tmp/full-workflow.json\n"
                ),
            )
            path = Path(metadata["path"])
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(text), 5001)  # final newline
            self.assertIn("/tmp/full-workflow.json", text)
            self.assertNotIn("nodes\": [", text)
            self.assertTrue((path.parent / "latest.json").is_file())


class FakeClient:
    def __init__(self):
        self.timeout = 180
        self.new_session_calls = 0
        self.prompts = []

    def new_session(self):
        self.new_session_calls += 1
        return {"success": True}

    def prompt(self, text):
        self.prompts.append(text)
        return {
            "text": "HANDOFF_READY",
            "usage": {"totalTokens": 2200},
            "context_window": 100000,
        }

    def close(self):
        pass


class ChatHandoffLifecycleTests(unittest.TestCase):
    def test_preemptive_handoff_resets_and_ingests(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session_root = root / "sessions"
            session_root.mkdir()
            with patch("comfy_pi_agent.chat._session_root", return_value=session_root), patch(
                "comfy_pi_agent.context_handoff.get_comfy_user_directory", return_value=root / "userdata"
            ):
                manager = ChatRuntimeManager()
                session = manager.store.create(title="Film")
                sid = session["session_id"]
                manager.store.append(sid, "user", "Continue the current movie project.")
                document = manager.store.append(sid, "assistant", "The current shot list is complete.")
                client = FakeClient()
                live = _LiveSession(
                    client=client,
                    project_directory="",
                    provider="",
                    model="",
                    executable="pi",
                    lock=threading.Lock(),
                    context_signature="old-scope",
                )
                with patch.object(
                    manager,
                    "_handoff_summarizer",
                    return_value=lambda source, budget: (
                        "# ComfyUI-Pi Continuity Handoff\n\n"
                        "## Primary Objective\nContinue the movie project.\n\n"
                        "## Next Actions\nGenerate the next scene.\n"
                    ),
                ):
                    updated, handoff = manager._preemptive_handoff(
                        session_id=sid,
                        live=live,
                        document=document,
                        prompt_result={"usage": {"totalTokens": 83000}, "context_window": 100000},
                        project_context="",
                        workflow_summary='{"node_count": 12}',
                        workflow_path="/tmp/workflow.json",
                        routed={},
                        threshold=0.825,
                        max_chars=8000,
                    )
                self.assertIsNotNone(handoff)
                self.assertEqual(client.new_session_calls, 1)
                self.assertTrue(any("Durable handoff file:" in p for p in client.prompts))
                self.assertTrue(any("BEGIN CONTINUITY HANDOFF" in p for p in client.prompts))
                self.assertTrue(handoff["ingested"])
                self.assertEqual(handoff["reset_method"], "new_session")
                self.assertTrue(live.handoff_ingested)
                self.assertIsNone(live.context_signature)
                self.assertEqual(updated["context_guard"]["handoff_count"], 1)
                self.assertLess(updated["context_guard"]["last_pressure"]["ratio"], 0.10)


if __name__ == "__main__":
    unittest.main()
