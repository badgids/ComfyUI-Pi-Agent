import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CHAT_STATE = {
  sessionId: null,
  busy: false,
  abortRequested: false,
  sessions: [],
  commands: [],
  commandIndex: -1,
  providers: [],
  models: [],
  modelCatalogLoaded: false,
  providerModelMemory: {},
};

const LOCAL_PROVIDERS = new Set(["llama.cpp", "ollama", "lm-studio", "vllm", "openai-compatible"]);
const LOCAL_PROVIDER_DEFAULTS = {
  "llama.cpp": "http://127.0.0.1:8080",
  "ollama": "http://127.0.0.1:11434",
  "lm-studio": "http://127.0.0.1:1234/v1",
  "vllm": "http://127.0.0.1:8000/v1",
  "openai-compatible": "http://127.0.0.1:8000/v1",
};

function isLocalProvider(value) {
  return LOCAL_PROVIDERS.has(String(value || ""));
}

function providerIdForSelector(selector) {
  const value = String(selector || "");
  if (value === "pi-default") return "";
  if (value === "openai-compatible") return "comfyui-local";
  const metadata = CHAT_STATE.providers.find((item) => String(item.selector || "") === value);
  return String(metadata?.provider || value);
}

function selectedProviderPayload(ui) {
  const selector = ui.provider.value;
  if (selector === "pi-default") return { provider: "", model: "", local_llm: {} };
  const provider = providerIdForSelector(selector);
  if (!isLocalProvider(selector)) {
    return { provider, model: ui.model.value || "", local_llm: {} };
  }
  return {
    provider,
    model: ui.model.value || "",
    local_llm: {
      enabled: true,
      kind: selector,
      base_url: ui.localBaseUrl.value.trim(),
      provider,
      model: ui.model.value || "",
      models: [...ui.model.options].map((option) => option.value).filter(Boolean),
      api_key_env: ui.localApiKeyEnv.value.trim(),
    },
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  if (!value) return "";
  try {
    return new Date(Number(value) * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

async function fetchJson(path, options = {}) {
  const response = await api.fetchApi(path, options);
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function fetchStatus() {
  return await fetchJson("/pi-agent/status");
}

function currentWorkflow() {
  try {
    return app.graph?.serialize?.() ?? null;
  } catch (error) {
    console.warn("Pi Agent could not serialize current workflow", error);
    return null;
  }
}

function copyText(text) {
  const value = String(text ?? "");
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(value).catch(() => fallbackCopy(value));
  }
  return fallbackCopy(value);
}

function fallbackCopy(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function ensureStyles() {
  if (document.getElementById("pi-agent-chat-styles")) return;
  const style = document.createElement("style");
  style.id = "pi-agent-chat-styles";
  style.textContent = `
    .pi-agent-shell { height: 100%; min-height: 420px; display: flex; flex-direction: column; color: var(--fg-color, inherit); background: var(--comfy-menu-bg, transparent); }
    .pi-agent-toolbar { display:flex; align-items:center; gap:6px; padding:8px; border-bottom:1px solid color-mix(in srgb, currentColor 15%, transparent); flex-wrap:wrap; }
    .pi-agent-title { font-weight:600; margin-right:auto; }
    .pi-agent-pill { font-size:11px; padding:2px 7px; border-radius:999px; border:1px solid color-mix(in srgb, currentColor 20%, transparent); opacity:.9; }
    .pi-agent-btn { border:1px solid color-mix(in srgb, currentColor 22%, transparent); background:color-mix(in srgb, currentColor 6%, transparent); color:inherit; border-radius:7px; padding:6px 9px; cursor:pointer; font:inherit; }
    .pi-agent-btn:hover { background:color-mix(in srgb, currentColor 11%, transparent); }
    .pi-agent-btn:disabled { opacity:.45; cursor:not-allowed; }
    .pi-agent-sessions { min-width:120px; max-width:210px; border:1px solid color-mix(in srgb, currentColor 22%, transparent); background:var(--comfy-menu-bg, inherit); color:inherit; border-radius:7px; padding:5px 7px; }
    .pi-agent-settings { padding:8px; border-bottom:1px solid color-mix(in srgb, currentColor 15%, transparent); display:grid; gap:7px; }
    .pi-agent-settings[hidden] { display:none; }
    .pi-agent-field { display:grid; gap:3px; }
    .pi-agent-field label { font-size:11px; opacity:.75; }
    .pi-agent-input { width:100%; box-sizing:border-box; border:1px solid color-mix(in srgb, currentColor 22%, transparent); background:color-mix(in srgb, currentColor 4%, transparent); color:inherit; border-radius:7px; padding:6px 8px; font:inherit; }
    .pi-agent-shell select { color-scheme:dark; background-color:var(--comfy-menu-bg, var(--bg-color, #202020)); color:var(--input-text, var(--fg-color, #f2f2f2)); }
    .pi-agent-shell select option, .pi-agent-shell select optgroup { background-color:var(--comfy-menu-bg, var(--bg-color, #202020)); color:var(--input-text, var(--fg-color, #f2f2f2)); }
    .pi-agent-check { display:flex; gap:7px; align-items:center; font-size:12px; }
    .pi-agent-messages { flex:1 1 auto; overflow:auto; padding:10px; display:flex; flex-direction:column; gap:10px; min-height:0; }
    .pi-agent-empty { margin:auto; max-width:300px; text-align:center; opacity:.72; line-height:1.45; padding:20px; }
    .pi-agent-message { max-width:94%; border:1px solid color-mix(in srgb, currentColor 14%, transparent); border-radius:10px; padding:9px 10px 7px; position:relative; line-height:1.45; user-select:text !important; -webkit-user-select:text !important; cursor:text; }
    .pi-agent-message.user { align-self:flex-end; background:color-mix(in srgb, #4f8cff 16%, transparent); }
    .pi-agent-message.assistant { align-self:flex-start; background:color-mix(in srgb, currentColor 5%, transparent); }
    .pi-agent-message.error { border-color:#c66; }
    .pi-agent-message-content { white-space:pre-wrap; overflow-wrap:anywhere; user-select:text !important; -webkit-user-select:text !important; }
    .pi-agent-message-content * { user-select:text !important; -webkit-user-select:text !important; }
    .pi-agent-message-content pre { overflow:auto; white-space:pre; padding:8px; border-radius:6px; background:color-mix(in srgb, currentColor 8%, transparent); }
    .pi-agent-message-content code { user-select:text !important; -webkit-user-select:text !important; }
    .pi-agent-message-meta { display:flex; align-items:center; gap:7px; margin-top:7px; font-size:10px; opacity:.62; }
    .pi-agent-copy { margin-left:auto; border:0; background:transparent; color:inherit; cursor:pointer; font-size:10px; padding:1px 3px; opacity:.8; }
    .pi-agent-composer { border-top:1px solid color-mix(in srgb, currentColor 15%, transparent); padding:8px; display:grid; gap:7px; }
    .pi-agent-textarea { width:100%; min-height:74px; max-height:220px; resize:vertical; box-sizing:border-box; border:1px solid color-mix(in srgb, currentColor 25%, transparent); background:color-mix(in srgb, currentColor 4%, transparent); color:inherit; border-radius:9px; padding:9px; font:inherit; line-height:1.4; user-select:text !important; -webkit-user-select:text !important; }
    .pi-agent-model-switcher { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1.25fr); gap:7px; align-items:end; }
    .pi-agent-model-switcher .pi-agent-field { min-width:0; }
    .pi-agent-model-switcher select { min-width:0; }
    .pi-agent-composer-actions { display:flex; gap:7px; align-items:center; }
    .pi-agent-send { margin-left:auto; min-width:72px; }
    .pi-agent-help { font-size:10px; opacity:.6; }
    .pi-agent-statusline { font-size:11px; min-height:16px; padding:0 2px; opacity:.72; }
    .pi-agent-command-menu { display:none; max-height:220px; overflow:auto; border:1px solid color-mix(in srgb, currentColor 22%, transparent); border-radius:8px; background:var(--comfy-menu-bg, #222); }
    .pi-agent-command-menu.open { display:block; }
    .pi-agent-command-item { padding:7px 9px; cursor:pointer; display:grid; gap:2px; }
    .pi-agent-command-item.active, .pi-agent-command-item:hover { background:color-mix(in srgb, currentColor 10%, transparent); }
    .pi-agent-command-name { font-family:monospace; font-size:12px; }
    .pi-agent-command-desc { font-size:10px; opacity:.68; }
    .pi-agent-local-box { border:1px solid color-mix(in srgb, currentColor 16%, transparent); border-radius:8px; padding:8px; display:grid; gap:7px; }
    .pi-agent-local-actions { display:flex; gap:6px; flex-wrap:wrap; }
    .pi-agent-local-status { font-size:10px; opacity:.72; white-space:pre-wrap; }
    .pi-agent-hidden { display:none !important; }
  `;
  document.head.appendChild(style);
}

function renderMessage(container, message) {
  const row = document.createElement("div");
  row.className = `pi-agent-message ${message.role === "user" ? "user" : "assistant"}${message.error ? " error" : ""}`;

  const content = document.createElement("div");
  content.className = "pi-agent-message-content";
  const text = String(message.content ?? "");
  if (message.role === "assistant" && app.extensionManager?.renderMarkdownToHtml) {
    content.innerHTML = app.extensionManager.renderMarkdownToHtml(text);
  } else {
    content.textContent = text;
  }

  const meta = document.createElement("div");
  meta.className = "pi-agent-message-meta";
  meta.innerHTML = `<span>${message.role === "user" ? "You" : "Pi Agent"}</span><span>${escapeHtml(formatTime(message.created_at))}</span>`;
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "pi-agent-copy";
  copy.textContent = "Copy";
  copy.title = "Copy this message. You can also select any text normally with the mouse.";
  copy.addEventListener("click", async () => {
    await copyText(text);
    copy.textContent = "Copied";
    setTimeout(() => { copy.textContent = "Copy"; }, 1200);
  });
  meta.appendChild(copy);

  row.append(content, meta);
  container.appendChild(row);
}

function scrollToBottom(el) {
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}


function updateContextPill(ui, guard = {}) {
  const pressure = guard?.last_pressure || {};
  const ratio = Number(pressure.ratio || 0);
  const threshold = Number(guard?.threshold || 0.825);
  const count = Number(guard?.handoff_count || 0);
  if (!ui.contextPill) return;
  if (ratio > 0) {
    ui.contextPill.textContent = `Context ${(ratio * 100).toFixed(1)}%`;
  } else {
    ui.contextPill.textContent = "Context --";
  }
  const last = guard?.last_handoff || {};
  const handoffInfo = count ? ` Handoffs: ${count}. Last: ${last.path || "saved"}.` : "";
  ui.contextPill.title = `Preemptive handoff threshold ${(threshold * 100).toFixed(1)}%.${handoffInfo}`;
}

async function loadSession(ui, sessionId) {
  const data = await fetchJson(`/pi-agent/chat/session/${encodeURIComponent(sessionId)}`);
  CHAT_STATE.sessionId = data.session.session_id;
  ui.messages.innerHTML = "";
  const messages = Array.isArray(data.session.messages) ? data.session.messages : [];
  if (!messages.length) {
    ui.messages.innerHTML = `<div class="pi-agent-empty">Chat with Pi here just like a normal AI assistant. Ask questions, paste text, or instruct it to help with your ComfyUI project. You do not need to add a node.</div>`;
  } else {
    for (const message of messages) renderMessage(ui.messages, message);
  }
  ui.project.value = data.session.project_directory || "";
  ui.scopedModels.value = data.session.scoped_models || "";
  const local = data.session.local_llm || {};
  const sessionProvider = String(data.session.provider || "");
  const providerSelector = local.kind && isLocalProvider(local.kind) ? local.kind : (sessionProvider || "pi-default");
  if (![...ui.provider.options].some((option) => option.value === providerSelector)) {
    const extras = [...CHAT_STATE.providers, { selector: providerSelector, provider: sessionProvider || providerSelector, label: providerSelector, source: "custom" }];
    populateProviderOptions(ui, extras, providerSelector);
  } else {
    ui.provider.value = providerSelector;
  }
  const sessionModel = String(data.session.model || local.model || "");
  if (isLocalProvider(providerSelector)) {
    const knownModels = Array.isArray(local.models) ? local.models : (sessionModel ? [sessionModel] : []);
    populateModels(ui, knownModels, sessionModel, "No saved local models");
    mergeProviderModels(sessionProvider || providerIdForSelector(providerSelector), knownModels);
  } else if (providerSelector === "pi-default") {
    populateModels(ui, [], "", "Pi default model");
  } else {
    const rows = modelsForProvider(providerSelector);
    populateModels(ui, rows.length ? rows : (sessionModel ? [{ provider: sessionProvider, id: sessionModel, name: sessionModel }] : []), sessionModel, "Open Model to load Pi models");
  }
  if (sessionProvider && sessionModel) CHAT_STATE.providerModelMemory[sessionProvider] = sessionModel;
  const defaultEndpoint = LOCAL_PROVIDER_DEFAULTS[providerSelector] || "";
  ui.localBaseUrl.value = local.base_url && local.base_url !== defaultEndpoint ? local.base_url : "";
  ui.localBaseUrl.placeholder = defaultEndpoint ? `Optional — default: ${defaultEndpoint}` : "Optional endpoint override";
  ui.localApiKeyEnv.value = local.api_key_env || "";
  updateProviderControls(ui);
  const guard = data.session.context_guard || {};
  ui.preemptiveHandoff.checked = guard.enabled !== false;
  ui.handoffThreshold.value = Number((guard.threshold ?? 0.825) * 100).toFixed(1);
  ui.handoffMaxChars.value = Number(guard.handoff_max_chars || 8000);
  updateContextPill(ui, guard);
  ui.sessionSelect.value = CHAT_STATE.sessionId;
  scrollToBottom(ui.messages);
  if (isLocalProvider(providerSelector)) {
    // The sidebar is already open: refresh the selected host now so stale saved
    // one-model catalogs do not survive across upgrades/restarts. This is not a
    // ComfyUI/plugin-startup probe; it occurs only when Pi Agent Chat is rendered.
    try {
      await applyProviderSelection(ui, { forceProbe: true, reloadCatalog: false });
    } catch (error) {
      ui.statusline.textContent = String(error);
    }
  }
}

async function refreshSessions(ui, preferredSessionId = null) {
  const data = await fetchJson("/pi-agent/chat/sessions");
  CHAT_STATE.sessions = data.sessions || [];
  ui.sessionSelect.innerHTML = "";
  for (const session of CHAT_STATE.sessions) {
    const option = document.createElement("option");
    option.value = session.session_id;
    option.textContent = session.title || "Chat";
    ui.sessionSelect.appendChild(option);
  }
  let target = preferredSessionId || CHAT_STATE.sessionId;
  if (!target && CHAT_STATE.sessions.length) target = CHAT_STATE.sessions[0].session_id;
  if (!target) {
    const created = await createSession(ui);
    target = created.session_id;
  }
  await loadSession(ui, target);
}

async function createSession(ui) {
  const data = await fetchJson("/pi-agent/chat/new", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: "New chat",
      project_directory: ui?.project?.value || "",
      ...(ui ? selectedProviderPayload(ui) : { provider: "", model: "", local_llm: {} }),
      scoped_models: ui?.scopedModels?.value || "",
    }),
  });
  CHAT_STATE.sessionId = data.session.session_id;
  return data.session;
}

function setBusy(ui, busy) {
  CHAT_STATE.busy = busy;
  ui.send.disabled = busy;
  ui.newChat.disabled = busy;
  ui.sessionSelect.disabled = busy;
  ui.provider.disabled = busy;
  ui.model.disabled = busy || ui.provider.value === "pi-default";
  ui.stop.classList.toggle("pi-agent-hidden", !busy);
  ui.statusline.textContent = busy ? "Pi is working…" : "";
}

async function sendMessage(ui) {
  const message = ui.textarea.value.trim();
  if (!message || CHAT_STATE.busy) return;
  if (!CHAT_STATE.sessionId) {
    const session = await createSession(ui);
    await refreshSessions(ui, session.session_id);
  }

  ui.textarea.value = "";
  if (ui.messages.querySelector(".pi-agent-empty")) ui.messages.innerHTML = "";
  renderMessage(ui.messages, { role: "user", content: message, created_at: Date.now() / 1000 });
  scrollToBottom(ui.messages);
  setBusy(ui, true);
  CHAT_STATE.abortRequested = false;

  const payload = {
    session_id: CHAT_STATE.sessionId,
    message,
    project_directory: ui.project.value.trim(),
    ...selectedProviderPayload(ui),
    scoped_models: ui.scopedModels.value.trim(),
    pi_executable: ui.executable.value.trim(),
    timeout_seconds: Number(ui.timeout.value || 180),
    workflow: ui.includeWorkflow.checked ? currentWorkflow() : null,
    project_context: ui.projectContext.value.trim(),
    preemptive_handoff: ui.preemptiveHandoff.checked,
    handoff_threshold_percent: Number(ui.handoffThreshold.value || 82.5),
    handoff_max_chars: Number(ui.handoffMaxChars.value || 8000),
  };

  try {
    const data = await fetchJson("/pi-agent/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!CHAT_STATE.abortRequested) {
      if (data.handoff) {
        ui.statusline.textContent = data.handoff.ingested
          ? "Context handoff created, reset, and ingested automatically."
          : "Context handoff created; automatic ingest needs attention.";
      }
      updateContextPill(ui, data.context_guard || data.session?.context_guard || {});
      if (data.ui_action === "copy_text") await copyText(data.message?.content || "");
      if (data.ui_action === "open_settings") ui.settings.hidden = false;
      if (data.ui_action === "open_local_llm") {
        ui.settings.hidden = false;
        ui.localBox.scrollIntoView?.({ block: "nearest" });
      }
      const targetSession = data.switch_session_id || data.session?.session_id || CHAT_STATE.sessionId;
      await refreshSessions(ui, targetSession);
    }
  } catch (error) {
    renderMessage(ui.messages, { role: "assistant", content: String(error), error: true, created_at: Date.now() / 1000 });
    ui.statusline.textContent = String(error);
  } finally {
    setBusy(ui, false);
    scrollToBottom(ui.messages);
    ui.textarea.focus();
  }
}

async function refreshCommandCatalog(ui) {
  try {
    const suffix = CHAT_STATE.sessionId ? `?session_id=${encodeURIComponent(CHAT_STATE.sessionId)}` : "";
    const data = await fetchJson(`/pi-agent/chat/commands${suffix}`);
    CHAT_STATE.commands = Array.isArray(data.commands) ? data.commands : [];
  } catch {
    CHAT_STATE.commands = [];
  }
}

function closeCommandMenu(ui) {
  CHAT_STATE.commandIndex = -1;
  ui.commandMenu.classList.remove("open");
  ui.commandMenu.innerHTML = "";
}

function commandMatches(text) {
  const value = String(text || "");
  if (!value.startsWith("/") || value.includes("\n")) return [];
  const body = value.slice(1);
  if (/\s/.test(body)) return [];
  const query = body.toLowerCase();
  return CHAT_STATE.commands.filter((item) => String(item.name || "").toLowerCase().startsWith(query)).slice(0, 24);
}

function renderCommandMenu(ui) {
  const matches = commandMatches(ui.textarea.value);
  if (!matches.length) return closeCommandMenu(ui);
  CHAT_STATE.commandIndex = Math.min(Math.max(CHAT_STATE.commandIndex, 0), matches.length - 1);
  ui.commandMenu.innerHTML = "";
  matches.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = `pi-agent-command-item${index === CHAT_STATE.commandIndex ? " active" : ""}`;
    row.innerHTML = `<span class="pi-agent-command-name">/${escapeHtml(item.name)}</span><span class="pi-agent-command-desc">${escapeHtml(item.description || item.usage || "")}</span>`;
    row.addEventListener("mousedown", (event) => {
      event.preventDefault();
      ui.textarea.value = `/${item.name} `;
      ui.textarea.focus();
      closeCommandMenu(ui);
    });
    ui.commandMenu.appendChild(row);
  });
  ui.commandMenu.classList.add("open");
}

function populateProviderOptions(ui, providers, selected = "") {
  const previous = selected || ui.provider.value || "pi-default";
  CHAT_STATE.providers = Array.isArray(providers) ? providers : [];
  ui.provider.innerHTML = "";
  const groups = [
    ["default", "Default"],
    ["local", "Local model hosts"],
    ["builtin", "Pi built-in providers"],
    ["custom", "Custom providers"],
  ];
  for (const [source, label] of groups) {
    const items = CHAT_STATE.providers.filter((item) => String(item.source || "custom") === source);
    if (!items.length) continue;
    const group = document.createElement("optgroup");
    group.label = label;
    for (const item of items) {
      const option = document.createElement("option");
      option.value = String(item.selector || item.provider || "");
      option.textContent = String(item.label || item.provider || item.selector || "Provider");
      group.appendChild(option);
    }
    ui.provider.appendChild(group);
  }
  const values = [...ui.provider.options].map((option) => option.value);
  if (previous && !values.includes(previous)) {
    const group = document.createElement("optgroup");
    group.label = "Current / custom";
    const option = document.createElement("option");
    option.value = previous;
    option.textContent = previous;
    group.appendChild(option);
    ui.provider.appendChild(group);
  }
  ui.provider.value = [...ui.provider.options].some((option) => option.value === previous) ? previous : "pi-default";
}

function populateModels(ui, models, selected = "", emptyText = "No models available") {
  const previous = selected || ui.model.value;
  const rows = Array.isArray(models) ? models : [];
  ui.model.innerHTML = "";
  for (const item of rows) {
    const modelId = typeof item === "string" ? String(item) : String(item?.id || "");
    if (!modelId) continue;
    const name = typeof item === "string" ? modelId : String(item?.name || modelId);
    const option = document.createElement("option");
    option.value = modelId;
    option.textContent = name === modelId ? modelId : `${name} (${modelId})`;
    ui.model.appendChild(option);
  }
  const values = [...ui.model.options].map((option) => option.value);
  if (previous && values.includes(previous)) ui.model.value = previous;
  if (!ui.model.options.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyText;
    ui.model.appendChild(option);
  }
}

function modelsForProvider(selector) {
  const provider = providerIdForSelector(selector);
  return CHAT_STATE.models.filter((item) => String(item?.provider || "") === provider);
}

function mergeProviderModels(provider, modelIds) {
  const providerId = String(provider || "");
  if (!providerId) return;
  CHAT_STATE.models = CHAT_STATE.models.filter((item) => String(item?.provider || "") !== providerId);
  for (const modelId of modelIds || []) {
    const value = String(modelId || "").trim();
    if (!value) continue;
    CHAT_STATE.models.push({ provider: providerId, id: value, name: value });
  }
}

async function refreshProviderMetadata(ui) {
  const data = await fetchJson("/pi-agent/model/providers");
  populateProviderOptions(ui, data.providers || [], ui.provider.value || "pi-default");
  return data;
}

async function refreshPiModelCatalog(ui, { force = false } = {}) {
  if (CHAT_STATE.modelCatalogLoaded && !force) return { providers: CHAT_STATE.providers, models: CHAT_STATE.models };
  const params = new URLSearchParams();
  if (CHAT_STATE.sessionId) params.set("session_id", CHAT_STATE.sessionId);
  if (ui.executable?.value?.trim()) params.set("pi_executable", ui.executable.value.trim());
  if (ui.project?.value?.trim()) params.set("project_directory", ui.project.value.trim());
  const data = await fetchJson(`/pi-agent/chat/model-catalog?${params.toString()}`);
  const selectedProvider = ui.provider.value || "pi-default";
  if (Array.isArray(data.providers) && data.providers.length) {
    populateProviderOptions(ui, data.providers, selectedProvider);
  }
  CHAT_STATE.models = Array.isArray(data.models) ? data.models : [];
  CHAT_STATE.modelCatalogLoaded = true;
  return data;
}

function updateProviderControls(ui) {
  const selector = ui.provider.value;
  const local = isLocalProvider(selector);
  const isDefault = selector === "pi-default";
  ui.model.disabled = isDefault;
  ui.localBox.hidden = !local;
  ui.providerAdvanced.hidden = !local;
  if (isDefault) {
    populateModels(ui, [], "", "Pi default model");
    ui.localStatus.textContent = "Pi will use its normal configured/default model.";
    return;
  }
  if (!local) {
    ui.localStatus.textContent = "";
    return;
  }
  const defaultEndpoint = LOCAL_PROVIDER_DEFAULTS[selector] || "";
  ui.localBaseUrl.placeholder = defaultEndpoint ? `Optional — default: ${defaultEndpoint}` : "Optional endpoint override";
  ui.localApiEnvRow.hidden = selector !== "openai-compatible";
}

async function persistModelSelection(ui, provider, model) {
  if (!CHAT_STATE.sessionId) await createSession(ui);
  const data = await fetchJson("/pi-agent/chat/model/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: CHAT_STATE.sessionId,
      provider: provider || "",
      model: model || "",
      timeout: Number(ui.timeout.value || 180),
    }),
  });
  if (provider && model) CHAT_STATE.providerModelMemory[provider] = model;
  return data;
}

async function applyProviderSelection(ui, { forceProbe = false, reloadCatalog = false } = {}) {
  const selector = ui.provider.value;
  updateProviderControls(ui);

  if (selector === "pi-default") {
    ui.provider.disabled = true;
    try {
      await persistModelSelection(ui, "", "");
      ui.statusline.textContent = "Using Pi's default configured model.";
    } finally {
      ui.provider.disabled = false;
      ui.model.disabled = true;
    }
    return;
  }

  if (isLocalProvider(selector)) {
    if (!CHAT_STATE.sessionId) await createSession(ui);
    ui.provider.disabled = true;
    ui.model.disabled = true;
    ui.localRefresh.disabled = true;
    ui.statusline.textContent = `Connecting to ${ui.provider.options[ui.provider.selectedIndex]?.text || selector}…`;
    try {
      const knownModels = forceProbe ? [] : [...ui.model.options].map((option) => option.value).filter(Boolean);
      const data = await fetchJson("/pi-agent/local-llm/configure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: CHAT_STATE.sessionId,
          kind: selector,
          base_url: ui.localBaseUrl.value.trim(),
          models: knownModels,
          model: ui.model.value || "",
          api_key_env: ui.localApiKeyEnv.value.trim(),
          reload_catalog: Boolean(reloadCatalog),
        }),
      });
      populateModels(ui, data.models || [], data.model || "", "No models reported by this host");
      mergeProviderModels(data.provider || providerIdForSelector(selector), data.models || []);
      CHAT_STATE.providerModelMemory[data.provider || providerIdForSelector(selector)] = data.model || "";
      const endpoint = data.base_url || LOCAL_PROVIDER_DEFAULTS[selector] || "";
      ui.statusline.textContent = `${(data.models || []).length} model(s) available from ${data.provider || selector}.`;
      ui.localStatus.textContent = `Endpoint: ${endpoint}\n${(data.models || []).length} model(s) reported by this host. The selected model is loaded only when needed.`;
      const defaultEndpoint = LOCAL_PROVIDER_DEFAULTS[selector] || "";
      ui.localBaseUrl.value = endpoint && endpoint !== defaultEndpoint ? endpoint : "";
    } catch (error) {
      populateModels(ui, [], "", "No models detected");
      ui.statusline.textContent = String(error);
      ui.localStatus.textContent = `${String(error)}\nThe endpoint is optional; expand Advanced only when your server is not on the common default.`;
    } finally {
      ui.provider.disabled = false;
      ui.localRefresh.disabled = false;
      ui.model.disabled = false;
    }
    return;
  }

  ui.provider.disabled = true;
  ui.model.disabled = true;
  ui.statusline.textContent = `Loading ${ui.provider.options[ui.provider.selectedIndex]?.text || selector} models from Pi…`;
  try {
    const catalog = await refreshPiModelCatalog(ui, { force: false });
    const rows = modelsForProvider(selector);
    const provider = providerIdForSelector(selector);
    const current = catalog.current || {};
    const preferred = CHAT_STATE.providerModelMemory[provider]
      || (String(current.provider || "") === provider ? String(current.model || "") : "")
      || rows[0]?.id
      || "";
    populateModels(ui, rows, preferred, "No available models for this provider");
    if (!rows.length) {
      ui.statusline.textContent = catalog.runtime_error
        ? `Pi model catalog unavailable: ${catalog.runtime_error}`
        : "No available models. Authenticate/configure this provider in Pi first.";
      return;
    }
    const model = ui.model.value || rows[0].id;
    ui.model.value = model;
    await persistModelSelection(ui, provider, model);
    ui.statusline.textContent = `Using ${provider}/${model}`;
  } catch (error) {
    populateModels(ui, [], "", "Unable to load Pi models");
    ui.statusline.textContent = String(error);
  } finally {
    ui.provider.disabled = false;
    ui.model.disabled = false;
  }
}

async function selectCurrentModel(ui) {
  const selector = ui.provider.value;
  const model = ui.model.value;
  if (selector === "pi-default" || !model) return;
  const provider = providerIdForSelector(selector);
  ui.model.disabled = true;
  try {
    if (isLocalProvider(selector)) {
      ui.statusline.textContent = `Preparing ${model}… This can take a while for a local model.`;
    }
    const data = await persistModelSelection(ui, provider, model);
    ui.statusline.textContent = `Using ${data.provider || provider}/${data.model || model}`;
    if (isLocalProvider(selector)) {
      const endpoint = ui.localBaseUrl.value.trim() || LOCAL_PROVIDER_DEFAULTS[selector] || "";
      ui.localStatus.textContent = `Endpoint: ${endpoint}\n${ui.model.options.length} model(s) reported by this host. Selected model is ready.`;
    }
  } catch (error) {
    ui.statusline.textContent = String(error);
  } finally {
    ui.model.disabled = false;
  }
}

async function abortMessage(ui) {
  if (!CHAT_STATE.sessionId || !CHAT_STATE.busy) return;
  CHAT_STATE.abortRequested = true;
  ui.statusline.textContent = "Stopping Pi…";
  try {
    await fetchJson("/pi-agent/chat/abort", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: CHAT_STATE.sessionId }),
    });
  } catch (error) {
    ui.statusline.textContent = String(error);
  }
}

async function clearChat(ui) {
  if (!CHAT_STATE.sessionId || CHAT_STATE.busy) return;
  await fetchJson("/pi-agent/chat/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: CHAT_STATE.sessionId }),
  });
  await refreshSessions(ui, CHAT_STATE.sessionId);
}

function buildSidebar(el) {
  ensureStyles();
  el.innerHTML = `
    <div class="pi-agent-shell">
      <div class="pi-agent-toolbar">
        <span class="pi-agent-title">Pi Agent Chat</span>
        <span id="pi-agent-runtime-pill" class="pi-agent-pill">Checking Pi…</span>
        <span id="pi-agent-context-pill" class="pi-agent-pill" title="Context pressure and preemptive handoff status">Context --</span>
        <button id="pi-agent-settings-toggle" class="pi-agent-btn" type="button" title="Chat settings">Settings</button>
      </div>
      <div class="pi-agent-toolbar">
        <select id="pi-agent-session-select" class="pi-agent-sessions" aria-label="Chat session"></select>
        <button id="pi-agent-new-chat" class="pi-agent-btn" type="button">New chat</button>
        <button id="pi-agent-copy-chat" class="pi-agent-btn" type="button">Copy chat</button>
        <button id="pi-agent-clear-chat" class="pi-agent-btn" type="button">Clear</button>
        <button id="pi-agent-delete-chat" class="pi-agent-btn" type="button">Delete</button>
      </div>
      <div id="pi-agent-chat-settings" class="pi-agent-settings" hidden>
        <div class="pi-agent-field">
          <label for="pi-agent-project">Project directory (optional)</label>
          <input id="pi-agent-project" class="pi-agent-input" type="text" placeholder="Use the current ComfyUI user directory when blank" />
        </div>
        <div class="pi-agent-field">
          <label for="pi-agent-project-context">Project notes/context (optional)</label>
          <textarea id="pi-agent-project-context" class="pi-agent-input" rows="3" placeholder="Paste a brief, task list, scene notes, or other context"></textarea>
        </div>
        <label class="pi-agent-check"><input id="pi-agent-include-workflow" type="checkbox" checked /> Include the current ComfyUI workflow with each message</label>
        <div class="pi-agent-help">Node-pack knowledge is loaded only when your message or attached workflow matches that integration.</div>
        <div id="pi-agent-local-box" class="pi-agent-local-box" hidden>
          <strong>Local model host — advanced</strong>
          <div class="pi-agent-help">Provider and Model are selected directly beneath the chat box. Normally you do not need anything here.</div>
          <details id="pi-agent-provider-advanced">
            <summary>Advanced: custom endpoint</summary>
            <div class="pi-agent-field"><label for="pi-agent-local-url">Endpoint override (optional)</label><input id="pi-agent-local-url" class="pi-agent-input" type="text" placeholder="Optional endpoint override" /></div>
            <div id="pi-agent-local-api-env-row" class="pi-agent-field"><label for="pi-agent-local-api-env">API-key environment variable (optional)</label><input id="pi-agent-local-api-env" class="pi-agent-input" type="text" placeholder="Example: LOCAL_LLM_API_KEY — raw keys are never stored here" /></div>
            <div class="pi-agent-local-actions"><button id="pi-agent-local-refresh" class="pi-agent-btn" type="button">Refresh models / apply endpoint</button></div>
          </details>
          <div id="pi-agent-local-status" class="pi-agent-local-status"></div>
        </div>
        <div class="pi-agent-field"><label for="pi-agent-scoped-models">Scoped model patterns (optional)</label><input id="pi-agent-scoped-models" class="pi-agent-input" type="text" placeholder="Example: llama.cpp/*,ollama/qwen*" /></div>
        <div class="pi-agent-field"><label for="pi-agent-executable">Pi executable override</label><input id="pi-agent-executable" class="pi-agent-input" type="text" placeholder="Leave blank for auto-discovery" /></div>
        <label class="pi-agent-check"><input id="pi-agent-preemptive-handoff" type="checkbox" checked /> Preemptive context handoff and reset</label>
        <div class="pi-agent-help">ComfyUI-Pi disables Pi's built-in auto-compaction. At the configured threshold it writes a compact handoff, starts a fresh Pi context, and ingests the handoff automatically.</div>
        <div class="pi-agent-field"><label for="pi-agent-handoff-threshold">Handoff threshold (%)</label><input id="pi-agent-handoff-threshold" class="pi-agent-input" type="number" min="80" max="95" step="0.5" value="82.5" /></div>
        <div class="pi-agent-field"><label for="pi-agent-handoff-max-chars">Maximum handoff size (characters)</label><input id="pi-agent-handoff-max-chars" class="pi-agent-input" type="number" min="4000" max="16000" step="500" value="8000" /></div>
        <div class="pi-agent-field"><label for="pi-agent-timeout">Timeout in seconds</label><input id="pi-agent-timeout" class="pi-agent-input" type="number" min="10" max="3600" value="180" /></div>
      </div>
      <div id="pi-agent-messages" class="pi-agent-messages" aria-live="polite"></div>
      <div class="pi-agent-composer">
        <textarea id="pi-agent-chat-input" class="pi-agent-textarea" placeholder="Message Pi Agent… Type / for Pi commands. Paste text normally. Enter sends; Shift+Enter adds a new line."></textarea>
        <div id="pi-agent-command-menu" class="pi-agent-command-menu" role="listbox" aria-label="Pi slash commands"></div>
        <div class="pi-agent-model-switcher" aria-label="Pi provider and model selection">
          <div class="pi-agent-field"><label for="pi-agent-provider">Provider</label><select id="pi-agent-provider" class="pi-agent-input"><option value="pi-default">Pi default / current configured model</option></select></div>
          <div class="pi-agent-field"><label for="pi-agent-model">Model</label><select id="pi-agent-model" class="pi-agent-input"><option value="">Pi default model</option></select></div>
        </div>
        <div id="pi-agent-statusline" class="pi-agent-statusline"></div>
        <div class="pi-agent-composer-actions">
          <span class="pi-agent-help">Text in the conversation is selectable and copyable.</span>
          <button id="pi-agent-stop" class="pi-agent-btn pi-agent-hidden" type="button">Stop</button>
          <button id="pi-agent-send" class="pi-agent-btn pi-agent-send" type="button">Send</button>
        </div>
      </div>
    </div>`;

  const ui = {
    sessionSelect: el.querySelector("#pi-agent-session-select"),
    newChat: el.querySelector("#pi-agent-new-chat"),
    copyChat: el.querySelector("#pi-agent-copy-chat"),
    clearChat: el.querySelector("#pi-agent-clear-chat"),
    deleteChat: el.querySelector("#pi-agent-delete-chat"),
    settingsToggle: el.querySelector("#pi-agent-settings-toggle"),
    settings: el.querySelector("#pi-agent-chat-settings"),
    project: el.querySelector("#pi-agent-project"),
    projectContext: el.querySelector("#pi-agent-project-context"),
    includeWorkflow: el.querySelector("#pi-agent-include-workflow"),
    provider: el.querySelector("#pi-agent-provider"),
    model: el.querySelector("#pi-agent-model"),
    scopedModels: el.querySelector("#pi-agent-scoped-models"),
    localBox: el.querySelector("#pi-agent-local-box"),
    providerAdvanced: el.querySelector("#pi-agent-provider-advanced"),
    localBaseUrl: el.querySelector("#pi-agent-local-url"),
    localApiEnvRow: el.querySelector("#pi-agent-local-api-env-row"),
    localApiKeyEnv: el.querySelector("#pi-agent-local-api-env"),
    localRefresh: el.querySelector("#pi-agent-local-refresh"),
    localStatus: el.querySelector("#pi-agent-local-status"),
    executable: el.querySelector("#pi-agent-executable"),
    preemptiveHandoff: el.querySelector("#pi-agent-preemptive-handoff"),
    handoffThreshold: el.querySelector("#pi-agent-handoff-threshold"),
    handoffMaxChars: el.querySelector("#pi-agent-handoff-max-chars"),
    timeout: el.querySelector("#pi-agent-timeout"),
    messages: el.querySelector("#pi-agent-messages"),
    textarea: el.querySelector("#pi-agent-chat-input"),
    commandMenu: el.querySelector("#pi-agent-command-menu"),
    statusline: el.querySelector("#pi-agent-statusline"),
    send: el.querySelector("#pi-agent-send"),
    stop: el.querySelector("#pi-agent-stop"),
    runtimePill: el.querySelector("#pi-agent-runtime-pill"),
    contextPill: el.querySelector("#pi-agent-context-pill"),
  };

  ui.settingsToggle.addEventListener("click", () => { ui.settings.hidden = !ui.settings.hidden; });
  ui.send.addEventListener("click", () => sendMessage(ui));
  ui.stop.addEventListener("click", () => abortMessage(ui));
  ui.provider.addEventListener("change", () => applyProviderSelection(ui, { forceProbe: true, reloadCatalog: false }));
  ui.model.addEventListener("change", () => selectCurrentModel(ui));
  ui.model.addEventListener("focus", async () => {
    const selector = ui.provider.value;
    if (CHAT_STATE.busy || selector === "pi-default" || isLocalProvider(selector) || CHAT_STATE.modelCatalogLoaded) return;
    const selected = ui.model.value;
    try {
      await refreshPiModelCatalog(ui, { force: false });
      populateModels(ui, modelsForProvider(selector), selected, "No available models for this provider");
    } catch (error) {
      ui.statusline.textContent = String(error);
    }
  });
  ui.localRefresh.addEventListener("click", () => applyProviderSelection(ui, { forceProbe: true, reloadCatalog: true }));
  ui.textarea.addEventListener("input", () => { CHAT_STATE.commandIndex = 0; renderCommandMenu(ui); });
  ui.textarea.addEventListener("keydown", (event) => {
    const menuOpen = ui.commandMenu.classList.contains("open");
    const matches = commandMatches(ui.textarea.value);
    if (menuOpen && event.key === "ArrowDown") {
      event.preventDefault();
      CHAT_STATE.commandIndex = Math.min(CHAT_STATE.commandIndex + 1, matches.length - 1);
      renderCommandMenu(ui);
      return;
    }
    if (menuOpen && event.key === "ArrowUp") {
      event.preventDefault();
      CHAT_STATE.commandIndex = Math.max(CHAT_STATE.commandIndex - 1, 0);
      renderCommandMenu(ui);
      return;
    }
    if (menuOpen && (event.key === "Tab" || (event.key === "Enter" && !event.shiftKey))) {
      const item = matches[CHAT_STATE.commandIndex];
      if (item) {
        event.preventDefault();
        const exact = ui.textarea.value.trim().toLowerCase() === `/${String(item.name || "").toLowerCase()}`;
        if (event.key === "Enter" && exact) {
          closeCommandMenu(ui);
          sendMessage(ui);
        } else {
          ui.textarea.value = `/${item.name} `;
          closeCommandMenu(ui);
        }
        return;
      }
    }
    if (event.key === "Escape" && menuOpen) {
      event.preventDefault();
      closeCommandMenu(ui);
      return;
    }
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendMessage(ui);
    }
  });
  ui.newChat.addEventListener("click", async () => {
    if (CHAT_STATE.busy) return;
    const session = await createSession(ui);
    await refreshSessions(ui, session.session_id);
    ui.textarea.focus();
  });
  ui.copyChat.addEventListener("click", async () => {
    if (!CHAT_STATE.sessionId) return;
    const data = await fetchJson(`/pi-agent/chat/session/${encodeURIComponent(CHAT_STATE.sessionId)}`);
    const transcript = (data.session.messages || []).map((message) => `${message.role === "user" ? "You" : "Pi Agent"}:\n${message.content || ""}`).join("\n\n");
    await copyText(transcript);
    ui.statusline.textContent = "Chat copied.";
    setTimeout(() => { if (!CHAT_STATE.busy) ui.statusline.textContent = ""; }, 1200);
  });
  ui.clearChat.addEventListener("click", () => clearChat(ui));
  ui.deleteChat.addEventListener("click", async () => {
    if (!CHAT_STATE.sessionId || CHAT_STATE.busy) return;
    await fetchJson(`/pi-agent/chat/session/${encodeURIComponent(CHAT_STATE.sessionId)}`, { method: "DELETE" });
    CHAT_STATE.sessionId = null;
    await refreshSessions(ui);
    ui.textarea.focus();
  });
  ui.sessionSelect.addEventListener("change", async () => {
    await loadSession(ui, ui.sessionSelect.value);
    await refreshCommandCatalog(ui);
  });

  return ui;
}

async function initializeSidebar(el) {
  const ui = buildSidebar(el);
  await refreshCommandCatalog(ui);
  try {
    await refreshProviderMetadata(ui);
  } catch (error) {
    ui.statusline.textContent = `Provider catalog unavailable: ${String(error)}`;
  }
  try {
    const status = await fetchStatus();
    const pi = status.pi || {};
    ui.runtimePill.textContent = pi.available ? "Pi available" : "Pi not configured";
    ui.runtimePill.title = pi.message || "";
    if (!pi.available) ui.statusline.textContent = pi.message || "Pi runtime is not configured.";
  } catch (error) {
    ui.runtimePill.textContent = "Status unavailable";
    ui.statusline.textContent = String(error);
  }
  try {
    await refreshSessions(ui);
  } catch (error) {
    ui.messages.innerHTML = `<div class="pi-agent-empty"><strong>Unable to load chats.</strong><br>${escapeHtml(error)}</div>`;
  }
  ui.textarea.focus();
}

app.registerExtension({
  name: "badgids.ComfyUI.PiAgent",
  settings: [
    {
      id: "PiAgent.UI.ShowSidebar",
      name: "Pi Agent: Show optional sidebar after restart",
      type: "boolean",
      defaultValue: false,
      tooltip: "Adds Pi Agent Chat to the ComfyUI sidebar. All Pi Agent features remain available as nodes when disabled."
    }
  ],
  commands: [
    {
      id: "pi-agent.show-status",
      label: "Show Pi Agent status",
      icon: "pi pi-info-circle",
      function: async () => {
        try {
          const data = await fetchStatus();
          const message = `Plugin ${data.plugin_version}. Pi runtime: ${data.pi?.available ? "available" : "not configured"}. Models detected: ${data.models?.total ?? 0}.`;
          app.extensionManager?.toast?.add?.({ severity: "info", summary: "Pi Agent", detail: message, life: 6000 });
        } catch (error) {
          app.extensionManager?.toast?.add?.({ severity: "error", summary: "Pi Agent", detail: String(error), life: 6000 });
        }
      }
    }
  ],
  menuCommands: [
    { path: ["Pi Agent"], commands: ["pi-agent.show-status"] }
  ],
  async setup() {
    const enabled = app.extensionManager?.setting?.get?.("PiAgent.UI.ShowSidebar") ?? false;
    if (!enabled || !app.extensionManager?.registerSidebarTab) return;
    app.extensionManager.registerSidebarTab({
      id: "pi-agent-sidebar",
      icon: "pi pi-comments",
      title: "Pi Agent",
      tooltip: "Chat with and instruct Pi Agent directly inside ComfyUI",
      type: "custom",
      render: async (el) => {
        await initializeSidebar(el);
      }
    });
  }
});
