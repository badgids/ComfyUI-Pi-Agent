import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const PROTOCOL = "comfyui-pi-browser-tools.v1";
const CONTRACT_REVISIONS = Object.freeze({ workflow_get_current_json: 2, apply_workflow_graph_patch: 3 });
const workflowIds = new WeakMap();
let workflowSerial = 0;
let pollTimer = null;
let busy = false;
let mutationActive = false;
const patchLedger = new Map();

function activeWorkflowObject() {
  const value = app.extensionManager?.workflow?.activeWorkflow;
  return value?.value || value || app.graph;
}

function workflowIdentity() {
  const target = activeWorkflowObject();
  if (!target || (typeof target !== "object" && typeof target !== "function")) return "";
  let value = workflowIds.get(target);
  if (!value) {
    workflowSerial += 1;
    value = `comfyui-pi-workflow:${Date.now().toString(36)}:${workflowSerial}`;
    workflowIds.set(target, value);
  }
  return value;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(canonical(value)));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join("");
}

function serializeWorkflow() {
  const workflow = app.graph?.serialize?.();
  if (!workflow || !Array.isArray(workflow.nodes)) throw new Error("The active ComfyUI workflow cannot be serialized.");
  return structuredClone(workflow);
}

function nodes() { return Array.isArray(app.graph?._nodes) ? app.graph._nodes : []; }
function nodeId(value) { return String(value?.id ?? value ?? ""); }
function findNode(id) { const wanted = String(id ?? ""); return nodes().find((node) => nodeId(node) === wanted) || null; }
function nodeType(node) { return String(node?.comfyClass || node?.type || ""); }
function graphLinks() {
  const links = app.graph?.links;
  if (!links) return [];
  if (typeof links.values === "function") return [...links.values()].filter(Boolean);
  return Object.values(links).filter(Boolean);
}
function selectedNodes() {
  const selected = app.canvas?.selected_nodes;
  if (selected instanceof Map) return [...selected.values()];
  if (selected && typeof selected === "object") return Object.values(selected);
  return [];
}

function graphChanged() { app.graph?.setDirtyCanvas?.(true, true); app.canvas?.setDirty?.(true, true); }
function nextPaint(frames = 3) { return new Promise((resolve) => { const step = (n) => n <= 0 ? resolve() : requestAnimationFrame(() => step(n - 1)); step(frames); }); }

function widgetValues(node) {
  return Object.fromEntries((node?.widgets || []).filter((w) => w?.name).map((w) => [String(w.name), w.value]));
}
function setValuesExact(node, values) {
  const pending = new Map(Object.entries(values || {}));
  for (const widget of node?.widgets || []) {
    if (!pending.has(String(widget.name))) continue;
    const value = pending.get(String(widget.name));
    widget.value = value;
    widget.callback?.(value, app.canvas, node, [0, 0], {});
    pending.delete(String(widget.name));
  }
  if (pending.size) throw Object.assign(new Error(`Widgets not found on ${nodeType(node)}: ${[...pending.keys()].join(", ")}`), { code: "widget_not_found" });
  graphChanged();
}
function slotIndex(items, request, fallbackKey) {
  if (Number.isInteger(request?.[fallbackKey])) return Number(request[fallbackKey]);
  const name = String(request?.name || request?.input || request?.output || "");
  if (!name) return -1;
  return (items || []).findIndex((item) => String(item?.name || "") === name);
}
function resolveRef(ref, aliases) {
  if (ref && Object.prototype.hasOwnProperty.call(ref, "node_id")) return findNode(ref.node_id);
  if (ref && Object.prototype.hasOwnProperty.call(ref, "alias")) return findNode(aliases.get(String(ref.alias)));
  if (typeof ref === "string" || typeof ref === "number") return findNode(ref);
  return null;
}

async function withMutationLock(operation) {
  if (mutationActive) throw Object.assign(new Error("Another ComfyUI-Pi canvas mutation is active."), { code: "canvas_mutation_busy", details: { retryable: true } });
  mutationActive = true;
  const canvas = app.canvas;
  const readOnlyBefore = Boolean(canvas?.read_only);
  if (canvas) canvas.read_only = true;
  try {
    return await operation();
  } finally {
    if (canvas) canvas.read_only = readOnlyBefore;
    mutationActive = false;
  }
}

async function currentJson(params = {}) {
  const workflow = serializeWorkflow();
  const result = {
    workflow,
    workflow_identity: workflowIdentity(),
    graph_hash: await sha256(workflow),
    selected_node_ids: selectedNodes().map(nodeId),
  };
  if (String(params.format || "workflow") === "api") {
    if (typeof app.graphToPrompt !== "function") throw new Error("This ComfyUI frontend does not expose graphToPrompt().");
    const prompt = await app.graphToPrompt();
    result.api_prompt = prompt?.output || prompt?.prompt || prompt;
  }
  return result;
}

function overview() {
  const allNodes = nodes(); const links = graphLinks();
  const byType = {};
  for (const node of allNodes) byType[nodeType(node)] = (byType[nodeType(node)] || 0) + 1;
  return { node_count: allNodes.length, link_count: links.length, node_types: byType, selected_node_ids: selectedNodes().map(nodeId) };
}
function workflowDiagram() {
  const lines = ["flowchart LR"];
  for (const node of nodes()) lines.push(`  n${nodeId(node).replace(/[^A-Za-z0-9_]/g, "_")}[\"${String(node.title || nodeType(node)).replaceAll('"', "'")}\"]`);
  for (const link of graphLinks()) lines.push(`  n${String(link.origin_id).replace(/[^A-Za-z0-9_]/g, "_")} --> n${String(link.target_id).replace(/[^A-Za-z0-9_]/g, "_")}`);
  return { diagram: lines.join("\n") };
}
function queryWorkflow(p) {
  let result = nodes();
  if (p.node_id != null) result = result.filter((n) => nodeId(n) === String(p.node_id));
  if (p.node_type) result = result.filter((n) => nodeType(n) === String(p.node_type));
  if (p.title) result = result.filter((n) => String(n.title || "").toLowerCase().includes(String(p.title).toLowerCase()));
  return { nodes: result.map((n) => ({ id: n.id, type: nodeType(n), title: n.title, pos: [...n.pos], size: [...n.size], values: widgetValues(n) })), count: result.length, links: graphLinks() };
}

function createNode(nodeTypeName, values = {}, position = null) {
  const node = globalThis.LiteGraph?.createNode?.(nodeTypeName);
  if (!node) throw Object.assign(new Error(`Installed frontend could not create node type ${nodeTypeName}.`), { code: "node_not_loaded" });
  if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) node.pos = [Number(position.x), Number(position.y)];
  app.graph.add(node);
  setValuesExact(node, values);
  graphChanged();
  return node;
}
function connectExact(source, sourceIndex, target, targetIndex) {
  if (!source || !target) throw new Error("Connection endpoint node is missing.");
  if (!source.outputs?.[sourceIndex]) throw new Error(`Source output ${sourceIndex} is absent on ${nodeType(source)}.`);
  if (!target.inputs?.[targetIndex]) throw new Error(`Target input ${targetIndex} is absent on ${nodeType(target)}.`);
  const link = source.connect(sourceIndex, target, targetIndex);
  if (link == null && target.inputs?.[targetIndex]?.link == null) throw new Error(`ComfyUI rejected ${nodeType(source)}:${sourceIndex} -> ${nodeType(target)}:${targetIndex}.`);
  graphChanged();
}
function removeNodeExact(node) { if (!node) throw new Error("Node does not exist."); app.graph.remove(node); graphChanged(); }

async function applyGraphPatch(request) {
  return withMutationLock(async () => {
    if (!request || typeof request !== "object" || !request.plan) {
      throw Object.assign(new Error("A canonical GraphPatch request is required."), { code: "invalid_graph_patch" });
    }
    const applicationId = String(request.application_id || "");
    const patchHash = String(request.patch_hash || "");
    if (!applicationId || !patchHash) {
      throw Object.assign(new Error("GraphPatch application_id and patch_hash are required."), { code: "invalid_graph_patch" });
    }
    const currentIdentity = workflowIdentity();
    if (request.plan.expected_workflow_identity && request.plan.expected_workflow_identity !== currentIdentity) {
      throw Object.assign(new Error("The active workflow changed since this patch was compiled."), {
        code: "workflow_identity_precondition_failed",
        details: { expected: request.plan.expected_workflow_identity, actual: currentIdentity },
      });
    }
    const ledgerKey = `${currentIdentity}|${applicationId}`;
    const existingLedger = patchLedger.get(ledgerKey);
    if (existingLedger) {
      if (existingLedger.patch_hash !== patchHash) {
        throw Object.assign(new Error("The application id was already used for a different patch."), { code: "idempotency_conflict" });
      }
      return {
        ...structuredClone(existingLedger.result),
        already_applied: true,
        verification: { ...existingLedger.result.verification, idempotency_verified: true },
      };
    }

    const before = serializeWorkflow();
    const beforeHash = await sha256(before);
    if (request.plan.expected_graph_hash && beforeHash !== request.plan.expected_graph_hash) {
      throw Object.assign(new Error("The canvas changed after this patch was compiled."), {
        code: "graph_precondition_failed",
        details: { expected_graph_hash: request.plan.expected_graph_hash, actual_graph_hash: beforeHash },
      });
    }

    const aliases = new Map();
    let mutationStarted = false;
    let expectedGuardHash = beforeHash;
    const verification = { valid: false, issues: [], preserve_unmentioned_state: true };
    const touchedExisting = new Set();
    const rememberRef = (ref) => {
      if (ref && Object.prototype.hasOwnProperty.call(ref, "node_id")) touchedExisting.add(String(ref.node_id));
    };
    for (const update of request.plan.update_nodes || []) rememberRef(update.ref);
    for (const removal of request.plan.remove_nodes || []) rememberRef(removal.ref);
    for (const edge of [...(request.plan.remove_edges || []), ...(request.plan.add_edges || [])]) {
      rememberRef(edge?.source?.ref || edge?.source);
      rememberRef(edge?.target?.ref || edge?.target);
    }
    const beforeNodes = new Map((before.nodes || []).map((node) => [String(node.id), structuredClone(node)]));
    const ownedEnvelopeFields = new Set(["nodes", "links", "last_node_id", "last_link_id", "revision"]);
    const workflowEnvelope = (workflow) => Object.fromEntries(
      Object.entries(workflow || {}).filter(([key]) => !ownedEnvelopeFields.has(key)),
    );
    const beforeEnvelope = workflowEnvelope(before);

    const assertMutationGuard = async (phase) => {
      if (workflowIdentity() !== currentIdentity) {
        throw Object.assign(new Error(`The active workflow changed during GraphPatch (${phase}).`), {
          code: "concurrent_workflow_edit",
          details: { phase, reason: "workflow_identity_changed" },
        });
      }
      const actual = await sha256(serializeWorkflow());
      if (actual !== expectedGuardHash) {
        throw Object.assign(new Error(`The canvas changed outside the guarded GraphPatch (${phase}).`), {
          code: "concurrent_workflow_edit",
          details: { phase, expected_graph_hash: expectedGuardHash, actual_graph_hash: actual },
        });
      }
    };
    const acceptMutationGuard = async () => {
      expectedGuardHash = await sha256(serializeWorkflow());
    };
    const same = (left, right) => JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
    const layoutMatches = (node, hint) => {
      if (!hint || typeof hint !== "object") return true;
      const close = (left, right) => Math.abs(Number(left) - Number(right)) <= 0.75;
      if (Number.isFinite(hint.x) && !close(node?.pos?.[0], hint.x)) return false;
      if (Number.isFinite(hint.y) && !close(node?.pos?.[1], hint.y)) return false;
      if (Number.isFinite(hint.width) && !close(node?.size?.[0], hint.width)) return false;
      if (Number.isFinite(hint.height) && !close(node?.size?.[1], hint.height)) return false;
      return true;
    };
    const edgeFacts = (edge) => {
      const source = resolveRef(edge?.source?.ref || edge?.source, aliases);
      const target = resolveRef(edge?.target?.ref || edge?.target, aliases);
      const out = Number(edge?.source?.output_index ?? edge?.output_index ?? -1);
      const inputRequest = edge?.target || edge;
      const inp = Number.isInteger(inputRequest?.socket_index)
        ? Number(inputRequest.socket_index)
        : Number.isInteger(inputRequest?.input_index)
          ? Number(inputRequest.input_index)
          : (target?.inputs || []).findIndex((item) => String(item?.name || "") === String(inputRequest?.name || inputRequest?.input || ""));
      return { source, target, out, inp };
    };
    const edgeExists = (edge) => {
      const { source, target, out, inp } = edgeFacts(edge);
      if (!source || !target || out < 0 || inp < 0) return false;
      return graphLinks().some((link) =>
        String(link.origin_id) === nodeId(source)
        && Number(link.origin_slot) === out
        && String(link.target_id) === nodeId(target)
        && Number(link.target_slot) === inp
      );
    };

    try {
      mutationStarted = true;
      for (const create of request.plan.create_nodes || []) {
        await assertMutationGuard(`before-create:${create.alias}`);
        const pos = create.layout_hint && Number.isFinite(create.layout_hint.x) && Number.isFinite(create.layout_hint.y)
          ? { x: create.layout_hint.x, y: create.layout_hint.y }
          : null;
        const node = createNode(String(create.node_type), create.values || {}, pos);
        aliases.set(String(create.alias), node.id);
        if (Number.isFinite(create.layout_hint?.width) && Number.isFinite(create.layout_hint?.height)) {
          node.setSize?.([Number(create.layout_hint.width), Number(create.layout_hint.height)]);
        }
        graphChanged();
        await nextPaint(1);
        await acceptMutationGuard();
      }
      for (const update of request.plan.update_nodes || []) {
        await assertMutationGuard(`before-update:${JSON.stringify(update.ref)}`);
        const node = resolveRef(update.ref, aliases);
        if (!node) throw new Error("Update target disappeared.");
        const actual = widgetValues(node);
        for (const [key, expected] of Object.entries(update.expected_values || {})) {
          if (!same(actual[key], expected)) {
            throw Object.assign(new Error(`Expected value for ${key} changed before apply.`), { code: "value_precondition_failed" });
          }
        }
        setValuesExact(node, update.set_values || {});
        if (Number.isFinite(update.layout_hint?.x) && Number.isFinite(update.layout_hint?.y)) {
          node.pos = [Number(update.layout_hint.x), Number(update.layout_hint.y)];
        }
        if (Number.isFinite(update.layout_hint?.width) && Number.isFinite(update.layout_hint?.height)) {
          node.setSize?.([Number(update.layout_hint.width), Number(update.layout_hint.height)]);
        }
        graphChanged();
        await nextPaint(1);
        await acceptMutationGuard();
      }
      for (const edge of request.plan.remove_edges || []) {
        await assertMutationGuard("before-remove-edge");
        const { target, inp } = edgeFacts(edge);
        if (target?.inputs?.[inp]?.link != null) target.disconnectInput?.(inp);
        graphChanged();
        await nextPaint(1);
        await acceptMutationGuard();
      }
      for (const edge of request.plan.add_edges || []) {
        await assertMutationGuard("before-add-edge");
        const { source, target, out, inp } = edgeFacts(edge);
        connectExact(source, out, target, inp);
        await nextPaint(1);
        await acceptMutationGuard();
      }
      for (const removal of request.plan.remove_nodes || []) {
        await assertMutationGuard(`before-remove:${JSON.stringify(removal.ref)}`);
        removeNodeExact(resolveRef(removal.ref, aliases));
        await nextPaint(1);
        await acceptMutationGuard();
      }
      graphChanged();
      await nextPaint(3);
      await assertMutationGuard("before-verification");

      for (const create of request.plan.create_nodes || []) {
        const node = resolveRef({ alias: create.alias }, aliases);
        if (!node || nodeType(node) !== String(create.node_type)) {
          verification.issues.push({ code: "created_node_mismatch", alias: create.alias });
          continue;
        }
        for (const [key, value] of Object.entries(create.values || {})) {
          if (!same(widgetValues(node)[key], value)) verification.issues.push({ code: "value_mismatch", alias: create.alias, key });
        }
        if (!layoutMatches(node, create.layout_hint)) verification.issues.push({ code: "layout_mismatch", alias: create.alias });
      }
      for (const update of request.plan.update_nodes || []) {
        const node = resolveRef(update.ref, aliases);
        if (!node || nodeType(node) !== String(update.node_type)) {
          verification.issues.push({ code: "updated_node_mismatch", ref: update.ref });
          continue;
        }
        for (const [key, value] of Object.entries(update.set_values || {})) {
          if (!same(widgetValues(node)[key], value)) verification.issues.push({ code: "updated_value_mismatch", ref: update.ref, key });
        }
        if (!layoutMatches(node, update.layout_hint)) verification.issues.push({ code: "updated_layout_mismatch", ref: update.ref });
      }
      for (const removal of request.plan.remove_nodes || []) {
        if (resolveRef(removal.ref, aliases)) verification.issues.push({ code: "removed_node_still_present", ref: removal.ref });
      }
      for (const edge of request.plan.add_edges || []) {
        if (!edgeExists(edge)) verification.issues.push({ code: "edge_missing_after_apply", source: edge.source, target: edge.target });
      }
      for (const edge of request.plan.remove_edges || []) {
        if (edgeExists(edge)) verification.issues.push({ code: "removed_edge_still_present", source: edge.source, target: edge.target });
      }

      const after = serializeWorkflow();
      const afterNodes = new Map((after.nodes || []).map((node) => [String(node.id), node]));
      if (request.plan.preserve_unmentioned_state !== false) {
        if (!same(beforeEnvelope, workflowEnvelope(after))) {
          verification.issues.push({ code: "workflow_envelope_changed" });
          verification.preserve_unmentioned_state = false;
        }
        for (const [id, beforeNode] of beforeNodes) {
          if (touchedExisting.has(id)) continue;
          const afterNode = afterNodes.get(id);
          if (!afterNode || !same(beforeNode, afterNode)) {
            verification.issues.push({ code: "unrelated_node_changed", node_id: id });
            verification.preserve_unmentioned_state = false;
          }
        }
      }

      verification.valid = verification.issues.length === 0;
      if (!verification.valid) {
        throw Object.assign(new Error("GraphPatch post-apply verification failed."), { code: "verification_failed", details: verification });
      }
      const result = {
        success: true,
        applied: true,
        already_applied: false,
        application_id: applicationId,
        patch_hash: patchHash,
        graph_hash_before: beforeHash,
        graph_hash_after: await sha256(after),
        workflow_identity: currentIdentity,
        aliases: Object.fromEntries(aliases),
        created_node_ids: [...aliases.values()],
        verification,
        rollback: { attempted: false, complete: true },
        queued: false,
      };
      patchLedger.set(ledgerKey, { patch_hash: patchHash, result: structuredClone(result) });
      while (patchLedger.size > 64) patchLedger.delete(patchLedger.keys().next().value);
      return result;
    } catch (error) {
      const rollback = {
        attempted: false,
        complete: true,
        snapshot_restored: false,
        hash_verified: false,
        expected_graph_hash: beforeHash,
        restored_graph_hash: null,
        errors: [],
      };
      if (mutationStarted) {
        rollback.attempted = true;
        try {
          await app.loadGraphData(structuredClone(before), false, false, null, {
            deferWarnings: true,
            skipAssetScans: true,
            silentAssetErrors: true,
          });
          await nextPaint(4);
          rollback.snapshot_restored = same(serializeWorkflow(), before);
        } catch (restoreError) {
          rollback.errors.push(String(restoreError));
        }
        try {
          rollback.restored_graph_hash = await sha256(serializeWorkflow());
          rollback.hash_verified = rollback.restored_graph_hash === beforeHash;
        } catch (hashError) {
          rollback.errors.push(String(hashError));
        }
        rollback.complete = rollback.snapshot_restored && rollback.hash_verified;
      }
      return {
        success: false,
        applied: false,
        already_applied: false,
        application_id: applicationId,
        patch_hash: patchHash,
        error: {
          code: error?.code || "graph_patch_failed",
          message: String(error?.message || error),
          details: error?.details,
        },
        verification,
        rollback,
        queued: false,
      };
    }
  });
}

function commandEntries() {
  const manager = app.extensionManager?.command;
  const values = manager?.commands?.value || manager?.commands || manager?.getCommands?.() || [];
  return Array.isArray(values) ? values : Object.values(values || {});
}
async function executeCommand(id) {
  const manager = app.extensionManager?.command;
  if (typeof manager?.execute === "function") return await manager.execute(String(id));
  if (typeof app.extensionManager?.invokeCommand === "function") return await app.extensionManager.invokeCommand(String(id));
  const command = commandEntries().find((item) => String(item?.id || item?.commandId || "") === String(id));
  if (typeof command?.function === "function") return await command.function();
  throw new Error(`Frontend command ${id!r} is unavailable.`);
}

async function screenshotCanvas(p) {
  const workflow = serializeWorkflow();
  const storageSnapshot = (storage) => {
    const result = {};
    try { for (let i = 0; i < storage.length; i += 1) { const key = storage.key(i); if (key != null) result[key] = storage.getItem(key); } } catch {}
    return result;
  };
  const response = await api.fetchApi("/pi-agent/screenshot/playwright", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      request: { mode: "workflow", padding_px: Number(p.padding_px ?? 80), pixel_ratio: Number(p.pixel_ratio ?? 1.5) },
      workflow,
      viewport: { width: Math.max(800, Number(window.innerWidth || 0)), height: Math.max(600, Number(window.innerHeight || 0)) },
      local_storage: storageSnapshot(window.localStorage),
      session_storage: storageSnapshot(window.sessionStorage),
      prefers_dark: Boolean(window.matchMedia?.("(prefers-color-scheme: dark)")?.matches),
    }),
  });
  if (!response.ok) {
    let message = `Playwright screenshot failed: HTTP ${response.status}`;
    try { const body = await response.json(); message = String(body?.error || message); } catch {}
    throw Object.assign(new Error(message), { code: "real_screenshot_failed" });
  }
  const blob = await response.blob();
  const bytes = new Uint8Array(await blob.arrayBuffer()); let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return {
    format: "png", mime_type: "image/png", size_bytes: bytes.length, base64_data: btoa(binary),
    width: Number(response.headers.get("X-ComfyUI-Pi-Width") || 0),
    height: Number(response.headers.get("X-ComfyUI-Pi-Height") || 0),
    capture_backend: String(response.headers.get("X-ComfyUI-Pi-Capture-Backend") || "playwright-page-screenshot"),
    real_frontend_capture: true,
  };
}


const handlers = {
  query_workflow: (p) => queryWorkflow(p), workflow_overview: () => overview(), workflow_diagram: () => workflowDiagram(),
  workflow_get_current_json: (p) => currentJson(p),
  workflow_load_json: (p) => withMutationLock(async () => { const workflow = p.workflow || p.json || p; await app.loadGraphData(structuredClone(workflow), false, false, null, { deferWarnings: true }); await nextPaint(3); return currentJson(); }),
  workflow_get_tabs: () => { const store = app.extensionManager?.workflow; const values = store?.workflows?.value || store?.workflows || store?.workflowTabs?.value || []; const active = activeWorkflowObject(); return { tabs: Array.isArray(values) ? values.map((item) => ({ id: item.id, name: item.name, path: item.path, active: item === active })) : [], active_workflow_identity: workflowIdentity() }; },
  workflow_close_current: () => executeCommand("Comfy.Workflow.Close"), workflow_duplicate_current: () => executeCommand("Comfy.Workflow.Duplicate"),
  frontend_list_commands: () => ({ commands: commandEntries().map((item) => ({ id: item?.id || item?.commandId, label: item?.label || item?.name })) }),
  frontend_execute_command: (p) => executeCommand(p.command_id || p.id),
  frontend_list_keybindings: () => ({ commands: commandEntries().map((item) => ({ id: item?.id || item?.commandId, keybinding: item?.keybinding || item?.defaultKeybinding || null })) }),
  find_node: (p) => { const result = queryWorkflow(p); return { node: result.nodes[0] || null, matches: result.nodes }; },
  create_nodes: (p) => withMutationLock(async () => { const items = p.nodes || p.items || []; const made = []; for (const item of items) { const node = createNode(String(item.node_type || item.type), item.values || item.parameters || {}, item.position || item.pos || null); made.push({ id: node.id, type: nodeType(node), position: { x: node.pos[0], y: node.pos[1] }, size: { width: node.size[0], height: node.size[1] } }); await nextPaint(1); } return made; }),
  remove_nodes: (p) => withMutationLock(async () => { for (const id of p.node_ids || p.ids || []) removeNodeExact(findNode(id)); return { success: true }; }),
  bypass_nodes: (p) => withMutationLock(async () => { for (const id of p.node_ids || p.ids || []) { const node = findNode(id); if (node) node.mode = globalThis.LiteGraph?.BYPASS ?? 4; } graphChanged(); return { success: true }; }),
  unbypass_nodes: (p) => withMutationLock(async () => { for (const id of p.node_ids || p.ids || []) { const node = findNode(id); if (node) node.mode = globalThis.LiteGraph?.ALWAYS ?? 0; } graphChanged(); return { success: true }; }),
  pin_nodes: (p) => withMutationLock(async () => { for (const id of p.node_ids || p.ids || []) { const node = findNode(id); if (node) { node.flags = node.flags || {}; node.flags.pinned = true; } } graphChanged(); return { success: true }; }),
  unpin_nodes: (p) => withMutationLock(async () => { for (const id of p.node_ids || p.ids || []) { const node = findNode(id); if (node?.flags) delete node.flags.pinned; } graphChanged(); return { success: true }; }),
  select_nodes: (p) => withMutationLock(async () => { app.canvas?.deselectAllNodes?.(); for (const id of p.node_ids || p.ids || []) { const node = findNode(id); if (node) app.canvas?.selectNode?.(node, true); } return { selected_node_ids: selectedNodes().map(nodeId) }; }),
  get_current_node_selection: () => ({ nodes: selectedNodes().map((n) => ({ id: n.id, type: nodeType(n), title: n.title, values: widgetValues(n) })) }),
  focus_on_nodes: async (p) => { const target = (p.node_ids || []).map(findNode).filter(Boolean); if (target.length && typeof app.canvas?.fitViewToNodes === "function") app.canvas.fitViewToNodes(target); else { try { await executeCommand("Comfy.Canvas.FitView"); } catch { app.canvas?.centerOnNode?.(target[0]); } } await nextPaint(2); return { success: true }; },
  take_screenshot: screenshotCanvas,
  get_node_values: (p) => { const node = findNode(p.node_id || p.id); if (!node) throw new Error("Node not found."); return { node_id: node.id, node_type: nodeType(node), values: widgetValues(node) }; },
  set_node_values: (p) => withMutationLock(async () => { const node = findNode(p.node_id || p.id); if (!node) throw new Error("Node not found."); setValuesExact(node, p.values || p.parameters || {}); return { node_id: node.id, values: widgetValues(node) }; }),
  get_node_slots: (p) => { const node = findNode(p.node_id || p.id); if (!node) throw new Error("Node not found."); return { node_id: node.id, inputs: (node.inputs || []).map((x, i) => ({ index: i, name: x.name, type: x.type, link: x.link })), outputs: (node.outputs || []).map((x, i) => ({ index: i, name: x.name, type: x.type, links: x.links || [] })) }; },
  connect_nodes: (p) => withMutationLock(async () => { const source = findNode(p.source_node_id || p.source); const target = findNode(p.target_node_id || p.target); const out = Number.isInteger(p.source_output_index) ? p.source_output_index : slotIndex(source?.outputs, { name: p.source_output || p.output }, "output_index"); const inp = Number.isInteger(p.target_input_index) ? p.target_input_index : slotIndex(target?.inputs, { name: p.target_input || p.input }, "input_index"); connectExact(source, out, target, inp); return { success: true, source_node_id: source.id, source_output_index: out, target_node_id: target.id, target_input_index: inp }; }),
  connect_nodes_batch: (p) => withMutationLock(async () => { const results = []; for (const item of p.connections || p.items || []) { const source = findNode(item.source_node_id || item.source); const target = findNode(item.target_node_id || item.target); const out = Number.isInteger(item.source_output_index) ? item.source_output_index : slotIndex(source?.outputs, { name: item.source_output || item.output }, "output_index"); const inp = Number.isInteger(item.target_input_index) ? item.target_input_index : slotIndex(target?.inputs, { name: item.target_input || item.input }, "input_index"); connectExact(source, out, target, inp); results.push({ source_node_id: source.id, source_output_index: out, target_node_id: target.id, target_input_index: inp }); } return { success: true, connections: results }; }),
  auto_connect_workflow: (p) => withMutationLock(async () => { const order = (p.node_ids || []).map(findNode).filter(Boolean); const made = []; for (let i = 0; i < order.length - 1; i++) { const source = order[i], target = order[i + 1]; let pair = null; for (let o = 0; o < (source.outputs || []).length && !pair; o++) for (let j = 0; j < (target.inputs || []).length; j++) if (!target.inputs[j].link && (source.outputs[o].type === target.inputs[j].type || source.outputs[o].type === "*" || target.inputs[j].type === "*")) { pair = [o, j]; break; } if (pair) { connectExact(source, pair[0], target, pair[1]); made.push({ source: source.id, output_index: pair[0], target: target.id, input_index: pair[1] }); } } return { connections: made }; }),
  get_layout: (p) => ({ nodes: (p.node_ids?.length ? p.node_ids.map(findNode).filter(Boolean) : nodes()).map((n) => ({ id: n.id, type: nodeType(n), position: { x: n.pos[0], y: n.pos[1] }, size: { width: n.size[0], height: n.size[1] } })) }),
  modify_layout: (p) => withMutationLock(async () => { for (const item of p.nodes || p.items || p.layout || []) { const node = findNode(item.node_id || item.id); if (!node) continue; if (Number.isFinite(item.x) && Number.isFinite(item.y)) node.pos = [Number(item.x), Number(item.y)]; if (Number.isFinite(item.width) && Number.isFinite(item.height)) node.setSize?.([Number(item.width), Number(item.height)]); } graphChanged(); return handlers.get_layout({}); }),
  queue_workflow: async (p) => { if (typeof app.queuePrompt !== "function") throw new Error("ComfyUI queuePrompt is unavailable."); const result = await app.queuePrompt(Number(p.number ?? 0), Number(p.batch_count || p.batchCount || 1)); return { queued: true, result }; },
  cancel_workflow: async () => { if (typeof api.interrupt === "function") await api.interrupt(); else await api.fetchApi("/interrupt", { method: "POST" }); return { cancelled: true }; },
  enable_auto_queue: async () => { const settings = app.extensionManager?.queueSettings; if (settings && "mode" in settings) settings.mode = "instant"; return { enabled: true }; },
  disable_auto_queue: async () => { const settings = app.extensionManager?.queueSettings; if (settings && "mode" in settings) settings.mode = "disabled"; return { enabled: false }; },
  set_batch_count: async (p) => { const value = Math.max(1, Number(p.batch_count || p.count || 1)); if (app.ui?.batchCount != null) app.ui.batchCount = value; if (app.extensionManager?.queueSettings) app.extensionManager.queueSettings.batchCount = value; return { batch_count: value }; },
  get_queue_status: () => ({ running: api.clientId ? true : null, auto_queue: app.extensionManager?.queueSettings?.mode ?? null, batch_count: app.extensionManager?.queueSettings?.batchCount ?? app.ui?.batchCount ?? null }),
  view_node_mask: async (p) => { const node = findNode(p.node_id || p.id); if (!node) throw new Error("Node not found."); if (typeof node.getMaskPreview === "function") return await node.getMaskPreview(); throw Object.assign(new Error("This installed node/frontend does not expose a readable mask preview contract."), { code: "mask_preview_unavailable" }); },
  edit_node_mask: async (p) => { const node = findNode(p.node_id || p.id); if (!node) throw new Error("Node not found."); if (typeof node.editMask === "function") return await node.editMask(p); throw Object.assign(new Error("This installed node/frontend does not expose a programmatic mask editor contract."), { code: "mask_edit_unavailable" }); },
  confirm_mask_review: async (p) => ({ confirmed: Boolean(p.approved ?? p.confirmed), review_token: p.review_token || p.token || null }),
  place_chat_image_in_node: async (p) => { const node = findNode(p.node_id || p.id); if (!node) throw new Error("Node not found."); const widget = (node.widgets || []).find((item) => ["image", "filename"].includes(String(item.name))); if (!widget) throw new Error("Selected node has no image/filename widget."); widget.value = p.filename || p.image || p.value; widget.callback?.(widget.value, app.canvas, node, [0, 0], {}); graphChanged(); return { node_id: node.id, value: widget.value }; },
  apply_workflow_graph_patch: applyGraphPatch,
};

async function executeBrowserTool(request) {
  const name = String(request?.tool_name || ""); const handler = handlers[name];
  if (!handler) throw Object.assign(new Error(`Browser tool ${name} is not implemented by this frontend contract.`), { code: "browser_tool_not_supported" });
  const required = Number(request?.contract_revision || 1); const actual = Number(CONTRACT_REVISIONS[name] || 1);
  if (actual < required) throw Object.assign(new Error(`Browser contract ${name} revision ${actual} is older than required ${required}.`), { code: "frontend_contract_too_old", details: { required, actual } });
  return await handler(request.parameters || {});
}

async function complete(request, payload) {
  await api.fetchApi(`/pi-agent/mcp/browser/complete/${encodeURIComponent(request.request_id)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}
async function tick() {
  if (busy) return; busy = true;
  try {
    const response = await api.fetchApi("/pi-agent/mcp/browser/pending"); const data = await response.json(); const request = data?.request;
    if (!request) return;
    try { const result = await executeBrowserTool(request); await complete(request, { success: true, data: result }); }
    catch (error) { await complete(request, { success: false, error: String(error?.message || error), error_code: String(error?.code || "tool_execution_failed"), error_details: error?.details || null }); }
  } catch {} finally { busy = false; }
}
function startPolling() { if (pollTimer) return; tick(); pollTimer = setInterval(tick, 350); }

app.registerExtension({
  name: "ComfyUI.PiAgent.MCPBridge",
  async setup() {
    const supportedTools = Object.keys(handlers).sort();
    try {
      await api.fetchApi("/pi-agent/mcp/browser/hello", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ protocol: PROTOCOL, protocol_revision: 1, supported_tools: supportedTools, contract_revisions: CONTRACT_REVISIONS, workflow_identity: workflowIdentity() }) });
    } catch (error) { console.warn("ComfyUI-Pi MCP browser bridge hello failed", error); }
    startPolling();
  },
});
