# Dynamic MCP compatibility tools

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Related: Architecture](architecture.md) · [Related: Small local model reliability](small-model-reliability.md)
<!-- DOC_NAV_END -->

ComfyUI-Pi exposes an optional MCP stdio adapter and a Pi-native dynamic tool bridge over the same service layer. The compatibility catalog preserves the **128 current ComfyUI_FL-MCP public tool names** while preventing a weak/local model from receiving all of them at once.

## Dynamic exposure contract

The complete catalog is always installed, but only a bounded subset is visible to the LLM:

```text
user request
    ↓
deterministic host-side text router
    ↓
activate only matching tool family/names
    ↓
Pi sees the relevant exact tools
```

Three small meta-tools are always available in Pi:

- `comfyui_tool_search` searches the complete compatibility catalog without activating it.
- `comfyui_tool_activate` exposes exact names or one capability family for the current Pi session.
- `comfyui_tool_call` can discover-and-call an exact hidden tool in the same model turn and then activates that exact name for later calls.

The Pi dynamic extension caps the visible compatibility surface at 48 activated exact tools per session. Normal deterministic routing activates at most 24 for one user request. This limit is intentionally separate from the complete 128-tool catalog.

The standalone MCP stdio server starts with the three meta-tools plus `mcp_capability_audit`. Under current MCP `2026-07-28`, that `tools/list` stays deterministic and cacheable because the protocol core is stateless. `comfyui_tool_search` returns the hidden exact names and compact schemas, and `comfyui_tool_call` can invoke any of the 128 names immediately. An external client may also call a hidden exact name directly; the dispatcher accepts it even though it was not listed.

For backward-compatible 2025-era MCP clients that still use `initialize`, the adapter enters legacy session mode and can emit `notifications/tools/list_changed` as exact names/families are activated. Pi itself does not depend on MCP session state: it registers the relevant exact tools directly before the model turn.

For clients that require a static compatibility surface, set:

```text
COMFYUI_PI_MCP_EXPOSE=all
```

before starting the stdio server. This exposes all 128 compatibility names to that external MCP client; it does **not** change Pi's bounded dynamic tool behavior.

## Start the standalone MCP server

Use the same Python environment that can import the installed ComfyUI-Pi package:

```bash
python -m comfy_pi_agent.mcp.server
```

The adapter has no mandatory FastMCP/FastAPI/Pydantic dependency. It uses MCP stdio framing and calls the running ComfyUI-Pi HTTP service for execution.

The current ComfyUI web extension records the running HTTP origin and authoritative runtime paths in ComfyUI user data. An external client can explicitly override the origin with:

```text
COMFYUI_PI_BASE_URL=http://host:port
```

This is configuration, not a hardcoded install path. ComfyUI-Pi never writes a personal machine path into project source.

## Tool families

The 128 compatibility names are divided into lazily imported families:

- utility and capability audit;
- public web search/fetch;
- live workflow/canvas operations;
- deterministic graph compilation/application;
- saved workflow files;
- ComfyUI REST/jobs/history/settings/assets/resources;
- live node library and persistent schema knowledge;
- official Comfy Registry discovery;
- ComfyUI Manager inspection/mutation;
- real output/chat/mask image operations;
- custom-node development and Git operations;
- process control.

A family module is imported only when one of its tools is invoked. Merely loading ComfyUI-Pi does not import optional network, browser, Manager, coding, or MCP execution code.

## Graph transaction engine

Normal workflow creation/refinement should use:

```text
compile_workflow_refinement_spec
        ↓
apply_workflow_graph_patch
```

The compiler reads the current browser workflow and fresh `/object_info` catalog, resolves deterministic existing-node selectors (ID, exact title/type, or exactly one selected node), validates explicit values against live choices/ranges, and returns a graph patch pinned to:

- the active workflow identity;
- current serialized graph SHA-256;
- current normalized catalog SHA-256;
- current per-node schema SHA-256;
- exact source output and target input identities;
- requested widget values/layout;
- stable application ID and patch hash.

Directly compatible sockets are preferred. If the requested datatypes are incompatible, the compiler may insert **one** locally loaded converter only when exactly one safe non-partner/non-API/non-heavy candidate has a single compatible input and output. Multiple candidates become a user choice; no candidate is a validation failure. Set `allow_inferred_converters=false` for exact/no-extra-node requests.

`apply_workflow_graph_patch` refreshes the live catalog before browser mutation. A catalog or node-schema mismatch stops the operation before the canvas changes.

The browser then:

1. verifies the same workflow instance is active;
2. verifies the graph hash still matches;
3. acquires the single ComfyUI-Pi canvas mutation lock and temporarily makes the canvas read-only to user edits;
4. snapshots the complete serialized graph;
5. verifies a graph hash guard between every mutation stage so an outside edit cannot be folded into the transaction;
6. applies creates/updates/edges/removals;
7. verifies requested nodes, values, layouts, added/removed edges, removals, the unrelated workflow envelope, and every unrelated existing node;
8. records the idempotency result;
9. never queues the workflow as part of graph application.

Any post-mutation failure restores the complete original serialized snapshot with the real ComfyUI `loadGraphData()` path, then verifies both canonical snapshot equality and the original graph hash. Rollback is not reported complete unless both checks pass.

## Live node catalog and persistent knowledge

Fresh `/object_info` remains the only authority allowed to authorize a node class/schema for graph compilation.

The optional SQLite catalog stores the last valid generation for fast discovery and diagnostics. It records:

- catalog generation;
- normalized catalog hash and observed raw hash;
- node schema hash;
- native/custom/partner provenance;
- active/inactive status;
- first/last seen generation;
- searchable node metadata;
- schema-scoped verified lessons.

Volatile widget **default values** are normalized before schema hashing while the presence/type of the default, ports, constraints, enum choices, outputs, and other schema content remain part of the identity. A cached record or lesson can rank discovery; it cannot authorize execution against a different live schema hash. A connection lesson is written only after the real browser transaction succeeds and exact post-apply verification reports `valid=true`; it is stored under both endpoint node types and their exact current schema hashes.

## Runtime paths

The ComfyUI process writes a runtime context containing the actual running:

- user directory;
- input directory;
- output directory;
- temp directory;
- every live `folder_paths` category and registered root.

This preserves ComfyUI-Pi's live-registry-first behavior for `extra_model_paths.yaml`, `--extra-model-paths-config`, base/model directory overrides, custom `custom_nodes` roots, and user-defined categories. Child Pi/MCP processes consume that context rather than guessing default installation directories.

## Browser contract

`web/mcp_bridge.js` is loaded by ComfyUI as a separate frontend extension. It announces:

- browser protocol revision;
- exact browser tool names implemented by that page;
- per-tool contract revisions;
- current workflow identity.

Backend requests carry the required contract revision. A stale frontend fails with a structured contract error rather than silently running incompatible behavior.

Workflow/node screenshots remain fail-closed real-frontend captures. The MCP-compatible `take_screenshot` tool uses ComfyUI-Pi's Playwright screenshot endpoint; it does not substitute a synthetic workflow or node drawing.

## Safety gates

Tool risk and server capability gates are centralized. Unknown tools fail closed.

Default gates:

| Gate | Default | Covers |
|---|---:|---|
| workflow writes | enabled | canvas edits, workflow writes, queue/settings/history mutations |
| custom-node writes | disabled | source writes, patch application, pack creation |
| Git writes | disabled | custom-node commit/push |
| Manager mutations | disabled | install/update/uninstall/Manager queue mutation |
| process control | disabled | ComfyUI restart |

Environment overrides are:

```text
COMFYUI_PI_ENABLE_WORKFLOW_WRITES
COMFYUI_PI_ENABLE_CUSTOM_NODE_WRITES
COMFYUI_PI_ENABLE_GIT_WRITES
COMFYUI_PI_ENABLE_MANAGER_MUTATIONS
COMFYUI_PI_ENABLE_PROCESS_CONTROL
```

`mcp_capability_audit` reports the effective gates, browser contract, runtime context, dynamic-tool family counts, and the 128-name compatibility count.

## Compatibility behavior

The compatibility layer preserves public FL-MCP tool **names and intended operations**, but it does not pretend an unavailable runtime feature exists. For example, Manager v4 operations require an installed compatible Manager endpoint, mask editing requires a frontend/node contract that can actually edit the mask, and process restart requires a verified restart route. Those conditions fail explicitly instead of guessing or fabricating success.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Related: Architecture](architecture.md) · [Related: Small local model reliability](small-model-reliability.md)
<!-- DOC_NAV_FOOTER_END -->
