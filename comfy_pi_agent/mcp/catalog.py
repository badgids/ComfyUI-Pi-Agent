from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Iterable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    family: str
    description: str
    risk: str = "read_only"
    gate: str = ""
    browser: bool = False
    keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["input_schema"] = tool_input_schema(self.name)
        return value


def _words(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9]+", value.lower().replace("_", " "))))


def _specs(names: str, family: str, description: str, *, risk: str = "read_only", gate: str = "", browser: bool = False, keywords: tuple[str, ...] = ()) -> list[ToolSpec]:
    result: list[ToolSpec] = []
    for name in names.split():
        result.append(ToolSpec(name, family, description, risk, gate, browser, tuple(dict.fromkeys((*keywords, *_words(name))))))
    return result


_SPECS: list[ToolSpec] = []
_SPECS += _specs(
    "calculate_expressions wait generate_seed generate_float generate_int random_choice get_system_info mcp_capability_audit",
    "utility", "Utility, system information, deterministic calculation, or capability audit tool.",
    keywords=("utility", "system", "capability", "math", "random"),
)
_SPECS += _specs(
    "web_search web_fetch_page", "web", "Search or safely fetch public web content.",
    keywords=("web", "internet", "search", "fetch", "url"),
)
_SPECS += _specs(
    "query_workflow workflow_overview workflow_diagram workflow_get_current_json workflow_get_tabs find_node get_current_node_selection get_node_values get_node_slots get_layout frontend_list_commands frontend_list_keybindings take_screenshot",
    "workflow", "Inspect the live ComfyUI browser workflow, nodes, selection, layout, commands, or canvas.",
    browser=True, keywords=("workflow", "canvas", "node", "graph", "inspect", "layout"),
)
_SPECS += _specs(
    "workflow_load_json workflow_close_current workflow_duplicate_current create_nodes remove_nodes bypass_nodes unbypass_nodes pin_nodes unpin_nodes select_nodes focus_on_nodes set_node_values connect_nodes connect_nodes_batch auto_connect_workflow modify_layout frontend_execute_command",
    "workflow", "Mutate the live ComfyUI workflow/canvas using the real browser frontend.",
    risk="canvas_edit", gate="workflow_writes", browser=True,
    keywords=("workflow", "canvas", "node", "graph", "edit", "connect", "layout"),
)
_SPECS += _specs(
    "compile_workflow_refinement_spec plan_workflow_refinement plan_workflow compile_workflow_spec resolve_workflow_spec",
    "graph", "Compile or validate a live-schema-pinned deterministic workflow GraphPatch.",
    keywords=("workflow", "graph", "compile", "plan", "build", "refine"),
)
_SPECS += _specs(
    "apply_workflow_graph_patch apply_workflow_refinement apply_workflow_plan",
    "graph", "Atomically apply an exact workflow transaction with preconditions, verification, idempotency, and rollback.",
    risk="canvas_edit", gate="workflow_writes", browser=True,
    keywords=("workflow", "graph", "apply", "patch", "transaction", "rollback"),
)
_SPECS += _specs(
    "workflow_list_files workflow_read_file", "files", "Inspect saved ComfyUI workflow files from authoritative runtime workflow roots.",
    keywords=("workflow", "file", "saved", "json"),
)
_SPECS += _specs(
    "workflow_save_current workflow_rename_file workflow_delete_file", "files", "Write, rename, or delete a saved ComfyUI workflow file.",
    risk="approval_required", gate="workflow_writes", keywords=("workflow", "file", "save", "rename", "delete"),
)
_SPECS += _specs(
    "queue_workflow cancel_workflow enable_auto_queue disable_auto_queue set_batch_count get_queue_status",
    "workflow", "Control or inspect the live ComfyUI frontend queue.",
    risk="canvas_edit", gate="workflow_writes", browser=True,
    keywords=("queue", "run", "execute", "batch", "cancel"),
)
_SPECS += _specs(
    "comfy_jobs_list comfy_job_get get_execution_history get_queue_status_details get_execution_details comfy_status comfy_get_logs",
    "rest", "Inspect ComfyUI process, jobs, queue, history, execution state, or logs.",
    keywords=("queue", "job", "history", "execution", "status", "log"),
)
_SPECS += _specs(
    "comfy_free_memory", "rest", "Unload models and free ComfyUI memory.",
    risk="approval_required", gate="workflow_writes", keywords=("memory", "vram", "unload", "free"),
)
_SPECS += _specs(
    "comfy_history_delete comfy_settings_set delete_queue_items", "rest", "Mutate ComfyUI history, settings, or execution queue state.",
    risk="approval_required", gate="workflow_writes", keywords=("history", "settings", "queue", "delete", "clear"),
)
_SPECS += _specs(
    "comfy_settings_get comfy_models_list comfy_workflow_templates_list comfy_global_subgraphs_list comfy_node_replacements_get comfy_assets_list comfy_asset_get comfy_tags_list comfy_list_folders comfy_read_file comfy_search_resources extract_workflow_from_image",
    "rest", "Inspect ComfyUI settings, models, templates, subgraphs, assets, files, or embedded workflow metadata.",
    keywords=("model", "asset", "template", "file", "folder", "resource", "workflow"),
)
_SPECS += _specs(
    "comfy_upload_image comfy_upload_mask comfy_asset_upload comfy_assets_upload", "rest", "Upload an approved local file into the running ComfyUI instance.",
    risk="approval_required", gate="workflow_writes", keywords=("upload", "image", "mask", "asset"),
)
_SPECS += _specs(
    "node_library_status node_library_search node_knowledge_search node_library_get_details node_library_find_compatible",
    "node_library", "Inspect the live /object_info catalog or schema-scoped persistent discovery index.",
    keywords=("node", "library", "schema", "compatible", "catalog", "knowledge"),
)
_SPECS += _specs(
    "registry_search_packages registry_get_package", "registry", "Inspect official Comfy Registry package metadata.",
    keywords=("registry", "package", "custom", "node", "install"),
)
_SPECS += _specs(
    "manager_v4_status manager_v4_queue_status manager_v4_installed_packs manager_v4_snapshots manager_v4_node_mappings manager_v4_external_models manager_queue_status manager_search_nodes manager_get_node_mappings manager_check_updates manager_search_external_models",
    "manager", "Inspect the installed ComfyUI Manager, packs, mappings, snapshots, updates, or external models.",
    keywords=("manager", "pack", "custom", "node", "update", "model", "snapshot"),
)
_SPECS += _specs(
    "manager_queue_action manager_queue_start manager_queue_reset manager_v4_queue_action",
    "manager", "Mutate ComfyUI Manager queue or installation state.",
    risk="approval_required", gate="manager_mutations", keywords=("manager", "install", "update", "uninstall", "queue"),
)
_SPECS += _specs(
    "view_output_image view_chat_image view_node_mask", "images", "Read real output/chat/mask image content.",
    keywords=("image", "output", "mask", "view", "visual"),
)
_SPECS += _specs(
    "edit_node_mask confirm_mask_review place_chat_image_in_node", "images", "Edit or attach image/mask state through the real ComfyUI frontend.",
    risk="approval_required", gate="workflow_writes", browser=True, keywords=("image", "mask", "attach", "edit"),
)
_SPECS += _specs(
    "clear_error_buffer", "rest", "Clear ComfyUI-Pi's bounded runtime error buffer.",
    risk="approval_required", gate="workflow_writes", keywords=("error", "clear", "buffer"),
)
_SPECS += _specs(
    "custom_nodes_list_packs custom_nodes_read_file custom_nodes_read_file_excerpt custom_nodes_search custom_nodes_validate_pack custom_nodes_git_status custom_nodes_git_diff",
    "custom_nodes", "Inspect, search, validate, or diff installed custom-node packs across live custom_nodes roots.",
    keywords=("custom", "node", "code", "pack", "git", "file", "search"),
)
_SPECS += _specs(
    "custom_nodes_write_file custom_nodes_apply_patch custom_nodes_create_pack", "custom_nodes", "Write or patch a custom-node pack inside a live registered custom_nodes root.",
    risk="approval_required", gate="custom_node_writes", keywords=("custom", "node", "code", "write", "patch", "create"),
)
_SPECS += _specs(
    "custom_nodes_git_commit custom_nodes_git_push", "custom_nodes", "Commit or push a custom-node repository.",
    risk="approval_required", gate="git_writes", keywords=("custom", "node", "git", "commit", "push"),
)
_SPECS += _specs(
    "comfy_restart", "process", "Restart ComfyUI only through a verified supported process-control route.",
    risk="approval_required", gate="process_control", keywords=("restart", "process", "comfyui"),
)

TOOL_SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in _SPECS}
FL_MCP_COMPAT_TOOL_NAMES: tuple[str, ...] = tuple(sorted(TOOL_SPECS))
FAMILIES: tuple[str, ...] = tuple(sorted({spec.family for spec in TOOL_SPECS.values()}))

# Current FL-MCP main exposes 128 unique MCP tool names. Keep this assertion close to
# the compatibility catalog so an accidental omission is a hard development failure.
if len(TOOL_SPECS) != 128:  # pragma: no cover - import-time developer invariant
    raise RuntimeError(f"FL-MCP compatibility catalog must contain 128 tools, found {len(TOOL_SPECS)}")


def tool_spec(name: str) -> ToolSpec:
    try:
        return TOOL_SPECS[str(name)]
    except KeyError as exc:
        raise KeyError(f"Unknown ComfyUI-Pi MCP tool: {name}") from exc


def family_tools(family: str) -> list[ToolSpec]:
    wanted = str(family or "").strip().lower()
    return [spec for spec in TOOL_SPECS.values() if spec.family == wanted]


def search_tools(query: str, *, limit: int = 24, families: Iterable[str] | None = None) -> list[dict[str, object]]:
    terms = _words(str(query or ""))
    allowed = {str(item).strip().lower() for item in (families or []) if str(item).strip()}
    scored: list[tuple[int, str, ToolSpec]] = []
    for spec in TOOL_SPECS.values():
        if allowed and spec.family not in allowed:
            continue
        haystack = " ".join((spec.name, spec.family, spec.description, *spec.keywords)).lower()
        score = 0
        for term in terms:
            if term == spec.name.lower():
                score += 100
            elif term in spec.name.lower():
                score += 20
            if term == spec.family:
                score += 12
            score += 4 * sum(1 for token in spec.keywords if term == token)
            if term in haystack:
                score += 1
        if not terms:
            score = 1
        if score:
            scored.append((-score, spec.name, spec))
    scored.sort()
    return [item[2].to_dict() for item in scored[: max(1, min(int(limit), 128))]]


def route_text(text: str, *, limit: int = 24) -> list[str]:
    """Deterministically choose a bounded tool surface before a weak-model turn."""
    query = str(text or "").lower()
    if not query.strip():
        return []
    exact_mentions = [name for name in FL_MCP_COMPAT_TOOL_NAMES if name.lower() in query]
    family_terms = {
        "utility": ("capability audit", "system info", "calculate", "random seed", "random number"),
        "workflow": ("workflow", "canvas", "node", "connect", "layout", "selected", "queue", "run", "sampler"),
        "graph": ("build", "create workflow", "edit workflow", "rewire", "refine", "graph patch", "branch"),
        "node_library": ("node type", "node schema", "installed node", "compatible node", "object_info"),
        "rest": ("model", "checkpoint", "asset", "history", "job", "execution", "folder", "file", "template", "subgraph", "setting", "vram", "memory"),
        "manager": ("manager", "install node", "update node", "custom node pack", "external model"),
        "custom_nodes": ("custom node code", "custom_nodes", "write node", "patch node", "git diff", "git status", "git commit", "git push"),
        "images": ("image", "mask", "output", "visual", "attached image"),
        "registry": ("registry", "published package", "node package"),
        "web": ("web search", "internet", "fetch page", "website"),
        "process": ("restart comfyui", "restart comfy"),
        "files": ("saved workflow", "workflow file", "rename workflow", "delete workflow"),
    }
    families = [family for family, needles in family_terms.items() if any(needle in query for needle in needles)]
    if not families and not exact_mentions:
        return []
    results = search_tools(text, limit=limit * 2, families=families or None)
    # Always prefer the semantic transaction pair for workflow mutations/builds.
    preferred: list[str] = []
    if "graph" in families or any(word in query for word in ("create", "build", "edit", "change", "rewire", "add node", "remove node")):
        preferred.extend(["compile_workflow_refinement_spec", "apply_workflow_graph_patch"])
    names = exact_mentions + preferred + [str(item["name"]) for item in results]
    return list(dict.fromkeys(names))[: max(1, min(int(limit), 48))]


def tool_input_schema(name: str) -> dict[str, object]:
    """Compact JSON schemas for dynamically exposed tools.

    They intentionally accept additional properties for forward compatibility with
    upstream ComfyUI/Manager revisions and FL-MCP request envelopes.
    """
    n = str(name)
    obj = lambda props=None, required=None: {"type": "object", "properties": props or {}, "required": required or [], "additionalProperties": True}
    s = {"type": "string"}; i = {"type": "integer"}; num = {"type": "number"}; b = {"type": "boolean"}; arrs = {"type": "array", "items": s}
    if n in {"mcp_capability_audit","get_system_info","generate_seed","cancel_workflow","enable_auto_queue","disable_auto_queue","get_queue_status","comfy_settings_get","manager_queue_status","manager_queue_start","manager_queue_reset","manager_v4_status","manager_v4_queue_status","comfy_node_replacements_get","custom_nodes_list_packs","comfy_status"}: return obj()
    if n == "wait": return obj({"delay": num}, ["delay"])
    if n == "calculate_expressions": return obj({"expressions": {"type":"array","items":s}}, ["expressions"])
    if n in {"generate_float","generate_int"}: return obj({"min": num if n.endswith("float") else i, "max": num if n.endswith("float") else i})
    if n == "random_choice": return obj({"items": {"type":"array"}}, ["items"])
    if n in {"web_search"}: return obj({"query":s,"limit":i},["query"])
    if n in {"web_fetch_page"}: return obj({"url":s,"max_bytes":i},["url"])
    if n in {"find_node","query_workflow"}: return obj({"node_id":{},"node_type":s,"title":s,"find_last":b})
    if n in {"workflow_overview","workflow_diagram","workflow_get_current_json","workflow_get_tabs","frontend_list_commands","frontend_list_keybindings","take_screenshot","get_current_node_selection","get_layout"}: return obj({"format":s,"node_ids":arrs,"fit_view":b,"padding_px":i,"pixel_ratio":num})
    if n == "frontend_execute_command": return obj({"command_id":s},["command_id"])
    if n == "workflow_load_json": return obj({"workflow":{"type":"object"}},["workflow"])
    if n in {"workflow_read_file","workflow_delete_file"}: return obj({"path":s},["path"])
    if n == "workflow_save_current": return obj({"path":s},["path"])
    if n == "workflow_rename_file": return obj({"path":s,"new_path":s},["path","new_path"])
    if n in {"workflow_close_current","workflow_duplicate_current","workflow_list_files"}: return obj()
    if n == "create_nodes": return obj({"nodes":{"type":"array","items":{"type":"object","additionalProperties":True}}},["nodes"])
    if n in {"remove_nodes","bypass_nodes","unbypass_nodes","pin_nodes","unpin_nodes","select_nodes","focus_on_nodes"}: return obj({"node_ids":arrs},["node_ids"])
    if n in {"get_node_values","get_node_slots","view_node_mask"}: return obj({"node_id":{}},["node_id"])
    if n == "set_node_values": return obj({"node_id":{},"values":{"type":"object"}},["node_id","values"])
    if n == "connect_nodes": return obj({"source_node_id":{},"source_output":s,"source_output_index":i,"target_node_id":{},"target_input":s,"target_input_index":i},["source_node_id","target_node_id"])
    if n in {"connect_nodes_batch","auto_connect_workflow"}: return obj({"connections":{"type":"array","items":{"type":"object","additionalProperties":True}},"node_ids":arrs})
    if n == "modify_layout": return obj({"nodes":{"type":"array","items":{"type":"object","additionalProperties":True}}},["nodes"])
    if n in {"queue_workflow"}: return obj({"batch_count":i,"wait_for_completion":b,"timeout":num})
    if n == "set_batch_count": return obj({"batch_count":i},["batch_count"])
    if n in {"compile_workflow_refinement_spec","compile_workflow_spec","resolve_workflow_spec","plan_workflow","plan_workflow_refinement"}: return obj({"application_id":s,"nodes":{"type":"array"},"connections":{"type":"array"},"updates":{"type":"array"},"remove_nodes":{"type":"array"},"remove_edges":{"type":"array"}})
    if n in {"apply_workflow_graph_patch","apply_workflow_plan","apply_workflow_refinement"}: return obj({"application_id":s,"expected_catalog_hash":s,"patch_hash":s,"plan":{"type":"object"}})
    if n in {"comfy_job_get","get_execution_details"}: return obj({"job_id":s,"prompt_id":s})
    if n == "comfy_jobs_list": return obj({"limit":i,"offset":i,"status":s})
    if n == "get_execution_history": return obj({"prompt_id":s,"max_items":i})
    if n == "get_queue_status_details": return obj({"history_limit":i})
    if n == "comfy_free_memory": return obj({"unload_models":b,"free_memory":b})
    if n == "comfy_history_delete": return obj({"clear_all":b,"prompt_ids":arrs})
    if n == "comfy_settings_set": return obj({"id":s,"value":{},"settings":{"type":"object"}})
    if n == "delete_queue_items": return obj({"clear_all":b,"interrupt":b,"prompt_ids":arrs})
    if n == "comfy_models_list": return obj({"folder":s})
    if n == "comfy_workflow_templates_list": return obj({"pack":s,"filename":s})
    if n == "comfy_global_subgraphs_list": return obj({"id":s})
    if n in {"comfy_assets_list","comfy_tags_list"}: return obj({"limit":i,"offset":i,"prefix":s,"name_contains":s})
    if n in {"comfy_asset_get"}: return obj({"asset_id":s},["asset_id"])
    if n in {"comfy_upload_image","comfy_upload_mask","comfy_asset_upload","comfy_assets_upload"}: return obj({"path":s,"file_path":s,"image_path":s,"mask_path":s,"name":s},[])
    if n == "comfy_list_folders": return obj({"folder_type":s,"category":s,"pattern":s,"limit":i})
    if n == "comfy_read_file": return obj({"path":s,"max_bytes":i},["path"])
    if n == "comfy_search_resources": return obj({"query":s,"category":s,"folder_type":s,"limit":i},["query"])
    if n == "extract_workflow_from_image": return obj({"path":s,"image_path":s})
    if n == "node_library_status": return obj({"refresh":b})
    if n in {"node_library_search","node_knowledge_search"}: return obj({"query":s,"limit":i})
    if n in {"node_library_get_details","node_library_find_compatible"}: return obj({"node_type":s,"direction":s,"limit":i},["node_type"])
    if n == "registry_search_packages": return obj({"query":s,"limit":i})
    if n == "registry_get_package": return obj({"id":s,"node_id":s,"package":s})
    if n.startswith("manager_"):
        return obj({"action":s,"query":s,"mode":s,"client_id":s,"max_results":i,"payload":{"type":"object"}})
    if n in {"view_output_image"}: return obj({"filename":s,"subfolder":s,"type":s,"history_limit":i})
    if n == "view_chat_image": return obj({"path":s,"image_path":s})
    if n in {"edit_node_mask","confirm_mask_review","place_chat_image_in_node"}: return obj({"node_id":{},"approved":b,"review_token":s,"filename":s})
    if n in {"custom_nodes_read_file","custom_nodes_read_file_excerpt"}: return obj({"path":s,"start_line":i,"line_count":i},["path"])
    if n == "custom_nodes_search": return obj({"query":s,"path":s,"glob":s,"max_results":i},["query"])
    if n == "custom_nodes_write_file": return obj({"path":s,"content":s,"overwrite":b},["path","content"])
    if n == "custom_nodes_apply_patch": return obj({"patch":s},["patch"])
    if n == "custom_nodes_create_pack": return obj({"name":s,"category":s,"overwrite":b},["name"])
    if n in {"custom_nodes_validate_pack","custom_nodes_git_status","custom_nodes_git_diff","custom_nodes_git_push"}: return obj({"path":s},["path"])
    if n == "custom_nodes_git_commit": return obj({"path":s,"message":s},["path","message"])
    if n == "comfy_restart": return obj()
    return obj()
