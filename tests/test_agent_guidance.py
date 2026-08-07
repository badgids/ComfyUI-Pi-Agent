import unittest

from comfy_pi_agent.agent_guidance import (
    CORE_AGENT_CONTRACT,
    build_request_guidance,
    build_task_envelope,
    select_skills,
)


class AgentGuidanceTests(unittest.TestCase):
    def test_core_contract_is_small_but_explicit(self):
        self.assertLess(len(CORE_AGENT_CONTRACT), 3000)
        self.assertIn("Stay on the user's current task", CORE_AGENT_CONTRACT)
        self.assertIn("Inspect before guessing", CORE_AGENT_CONTRACT)
        self.assertIn("Never claim completion without evidence", CORE_AGENT_CONTRACT)

    def test_workflow_is_routed_without_llm_decision(self):
        matches = select_skills("fix it", workflow={"nodes": [], "links": []})
        names = [item.name for item in matches]
        self.assertIn("workflow-intelligence", names)
        self.assertLessEqual(len(names), 3)

    def test_specific_model_skill_beats_generic_router(self):
        matches = select_skills("Create a Qwen Image Edit workflow for this reference photo")
        names = [item.name for item in matches]
        self.assertIn("qwen-image-edit", names)
        self.assertNotIn("image-generation-router", names)

    def test_complete_production_routes_procedure(self):
        guidance = build_request_guidance("Compile the complete movie project and prepare Kdenlive")
        names = [item["name"] for item in guidance["loaded_skills"]]
        self.assertIn("complete-production", names)
        self.assertIn("kdenlive-handoff", names)
        self.assertIn("CURRENT JOB (do not drift)", guidance["task_envelope"])

    def test_task_envelope_has_completion_rule(self):
        matches = select_skills("repair this workflow", workflow={"nodes": [], "links": []})
        envelope = build_task_envelope("repair this workflow", matches, workflow_present=True)
        self.assertIn("Completion rule", envelope)
        self.assertIn("validate", envelope.lower())
        self.assertIn("do not drift", envelope.lower())


if __name__ == "__main__":
    unittest.main()
