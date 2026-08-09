import unittest

from comfy_pi_agent.mcp.catalog import (
    FL_MCP_COMPAT_TOOL_NAMES,
    FAMILIES,
    TOOL_SPECS,
    route_text,
    search_tools,
    tool_input_schema,
)
from comfy_pi_agent.mcp.security import SafetySettings, authorize_tool, classify_tool

EXPECTED_FL_MCP_TOOLS = {
    "calculate_expressions", "wait", "web_search", "web_fetch_page", "query_workflow",
    "workflow_overview", "workflow_diagram", "frontend_list_commands", "frontend_execute_command",
    "frontend_list_keybindings", "workflow_get_current_json", "workflow_load_json", "workflow_get_tabs",
    "workflow_list_files", "workflow_read_file", "workflow_save_current", "workflow_rename_file",
    "workflow_delete_file", "workflow_close_current", "workflow_duplicate_current", "find_node",
    "create_nodes", "remove_nodes", "bypass_nodes", "unbypass_nodes", "pin_nodes", "unpin_nodes",
    "select_nodes", "focus_on_nodes", "take_screenshot", "get_current_node_selection", "get_node_values",
    "view_node_mask", "edit_node_mask", "confirm_mask_review", "set_node_values", "connect_nodes",
    "get_node_slots", "connect_nodes_batch", "auto_connect_workflow", "get_layout", "modify_layout",
    "queue_workflow", "cancel_workflow", "enable_auto_queue", "disable_auto_queue", "set_batch_count",
    "get_queue_status", "comfy_jobs_list", "comfy_job_get", "comfy_free_memory", "comfy_history_delete",
    "comfy_settings_get", "comfy_settings_set", "manager_queue_action", "manager_queue_status",
    "manager_queue_start", "manager_queue_reset", "manager_v4_status", "manager_v4_queue_status",
    "manager_v4_queue_action", "manager_v4_installed_packs", "manager_v4_snapshots",
    "manager_v4_node_mappings", "manager_v4_external_models", "delete_queue_items", "generate_seed",
    "generate_float", "generate_int", "random_choice", "get_system_info", "mcp_capability_audit",
    "comfy_upload_image", "comfy_upload_mask", "comfy_models_list", "comfy_workflow_templates_list",
    "comfy_global_subgraphs_list", "comfy_node_replacements_get", "comfy_assets_list", "comfy_asset_get",
    "comfy_asset_upload", "comfy_assets_upload", "comfy_tags_list", "comfy_list_folders", "comfy_read_file",
    "comfy_search_resources", "extract_workflow_from_image", "node_library_status", "node_knowledge_search",
    "plan_workflow_refinement", "apply_workflow_refinement", "compile_workflow_refinement_spec",
    "apply_workflow_graph_patch", "plan_workflow", "compile_workflow_spec", "resolve_workflow_spec",
    "apply_workflow_plan", "node_library_search", "node_library_get_details", "node_library_find_compatible",
    "registry_search_packages", "registry_get_package", "manager_search_nodes", "manager_get_node_mappings",
    "manager_check_updates", "manager_search_external_models", "view_output_image", "view_chat_image",
    "place_chat_image_in_node", "get_execution_history", "get_queue_status_details", "get_execution_details",
    "clear_error_buffer", "custom_nodes_list_packs", "custom_nodes_read_file", "custom_nodes_read_file_excerpt",
    "custom_nodes_search", "custom_nodes_write_file", "custom_nodes_apply_patch", "custom_nodes_create_pack",
    "custom_nodes_validate_pack", "custom_nodes_git_status", "custom_nodes_git_diff", "custom_nodes_git_commit",
    "custom_nodes_git_push", "comfy_restart", "comfy_get_logs", "comfy_status",
}


class McpCatalogTests(unittest.TestCase):
    def test_exact_fl_compatibility_surface_matches_current_128_names(self):
        self.assertEqual(len(EXPECTED_FL_MCP_TOOLS), 128)
        self.assertEqual(set(FL_MCP_COMPAT_TOOL_NAMES), EXPECTED_FL_MCP_TOOLS)
        self.assertEqual(len(FL_MCP_COMPAT_TOOL_NAMES), 128)
        self.assertEqual(len(set(FL_MCP_COMPAT_TOOL_NAMES)), 128)
        for name in FL_MCP_COMPAT_TOOL_NAMES:
            self.assertEqual(tool_input_schema(name).get("type"), "object")

    def test_every_tool_has_family_and_fail_closed_risk(self):
        self.assertTrue(FAMILIES)
        self.assertEqual(classify_tool("not-real"), "approval_required")
        for name, spec in TOOL_SPECS.items():
            self.assertIn(spec.family, FAMILIES)
            allowed, reason = authorize_tool(name, SafetySettings())
            if spec.gate in {"custom_node_writes", "git_writes", "manager_mutations", "process_control"}:
                self.assertFalse(allowed, name)
                self.assertTrue(reason.endswith("_disabled"))

    def test_weak_model_routing_is_bounded_prefers_transaction_and_honors_exact_name(self):
        names = route_text("build a workflow with nodes and connect them", limit=24)
        self.assertLessEqual(len(names), 24)
        self.assertEqual(names[:2], ["compile_workflow_refinement_spec", "apply_workflow_graph_patch"])
        exact = route_text("please use custom_nodes_git_status for this", limit=24)
        self.assertEqual(exact[0], "custom_nodes_git_status")
        self.assertLessEqual(len(search_tools("manager install custom node", limit=8)), 8)


if __name__ == "__main__":
    unittest.main()
