import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CHAT_STATE = {
  sessionId: sessionStorage.getItem("ComfyUIPi.ActiveSession") || null,
  busy: false,
  abortRequested: false,
  sessions: [],
  commands: [],
  commandIndex: -1,
  providers: [],
  models: [],
  modelCatalogLoaded: false,
  providerModelMemory: {},
  modelPreparationPromise: null,
  view: sessionStorage.getItem("ComfyUIPi.ActiveView") === "chat" ? "chat" : "terminal",
  terminalSupported: false,
  terminal: null,
  terminalSocket: null,
  terminalAssetsPromise: null,
  terminalStarting: false,
  terminalStatusTimer: null,
  terminalRecoveryAttempts: 0,
  showReasoning: localStorage.getItem("ComfyUIPi.ShowReasoning") !== "false",
  showTools: localStorage.getItem("ComfyUIPi.ShowTools") !== "false",
};

function rememberSessionId(value) {
  const sessionId = String(value || "").trim();
  CHAT_STATE.sessionId = sessionId || null;
  if (sessionId) sessionStorage.setItem("ComfyUIPi.ActiveSession", sessionId);
  else sessionStorage.removeItem("ComfyUIPi.ActiveSession");
}

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

const SCREENSHOT_MIN_NODE_PADDING = 300;
const SCREENSHOT_EXACT_NODE_MODE = "node_exact";
const SCREENSHOT_DEFAULT_WORKFLOW_PADDING = 80;
let SCREENSHOT_WORKER_TIMER = null;
let SCREENSHOT_WORKER_BUSY = false;

function screenshotNextPaint(frames = 2) {
  return new Promise((resolve) => {
    const step = (remaining) => {
      if (remaining <= 0) {
        resolve();
        return;
      }
      requestAnimationFrame(() => step(remaining - 1));
    };
    step(frames);
  });
}

function screenshotGraphCanvas() {
  return app.canvas?.canvas ?? document.getElementById("graph-canvas");
}

function screenshotCaptureFrontendReady() {
  return Boolean(
    app?.canvas &&
    app?.rootGraph &&
    screenshotGraphCanvas() &&
    typeof app.loadGraphData === "function"
  );
}

function installPlaywrightCaptureBridge() {
  if (!screenshotCaptureFrontendReady()) return false;
  globalThis.__COMFYUI_PI_PLAYWRIGHT_CAPTURE_READY__ = true;
  globalThis.__COMFYUI_PI_PREPARE_PLAYWRIGHT_CAPTURE__ = preparePlaywrightWorkflowCapture;
  return true;
}

function screenshotGraphNodes() {
  const nodes = app.graph?._nodes;
  return Array.isArray(nodes) ? nodes : [];
}

function screenshotGraphBounds() {
  const items = [];
  for (const node of screenshotGraphNodes()) {
    const pos = node?.pos;
    const size = node?.size;
    if (!pos || !size) continue;
    const x = Number(pos[0]);
    const y = Number(pos[1]);
    const w = Number(size[0]);
    const h = Number(size[1]);
    if ([x, y, w, h].every(Number.isFinite) && w > 0 && h > 0) {
      items.push([x, y, w, h]);
    }
  }
  const groups = app.graph?._groups;
  if (Array.isArray(groups)) {
    for (const group of groups) {
      const pos = group?.pos;
      const size = group?.size;
      if (!pos || !size) continue;
      const x = Number(pos[0]);
      const y = Number(pos[1]);
      const w = Number(size[0]);
      const h = Number(size[1]);
      if ([x, y, w, h].every(Number.isFinite) && w > 0 && h > 0) {
        items.push([x, y, w, h]);
      }
    }
  }
  if (!items.length) return null;
  const minX = Math.min(...items.map((item) => item[0]));
  const minY = Math.min(...items.map((item) => item[1]));
  const maxX = Math.max(...items.map((item) => item[0] + item[2]));
  const maxY = Math.max(...items.map((item) => item[1] + item[3]));
  return [minX, minY, Math.max(1, maxX - minX), Math.max(1, maxY - minY)];
}

function screenshotFindGraphNode(nodeId) {
  const wanted = String(nodeId ?? "");
  return screenshotGraphNodes().find((node) => String(node?.id ?? "") === wanted) || null;
}

function screenshotInstalledNodeWorkflow(nodeType) {
  const type = String(nodeType || "").trim();
  if (!type) throw new Error("Exact installed-node capture requires node_type.");
  return {
    last_node_id: 1,
    last_link_id: 0,
    nodes: [{
      id: 1,
      type,
      pos: [0, 0],
      flags: {},
      order: 0,
      mode: 0,
      properties: {},
    }],
    links: [],
    groups: [],
    config: {},
    extra: { workflowRendererVersion: "Vue-corrected" },
    version: 0.4,
  };
}

function screenshotFitBounds(bounds, paddingPx, maxScale = 1.0) {
  const graphCanvas = screenshotGraphCanvas();
  const ds = app.canvas?.ds;
  if (!graphCanvas || !ds || !bounds) return false;
  const viewport = graphCanvas.getBoundingClientRect();
  const padding = Math.max(0, Number(paddingPx || 0));
  const availableW = Math.max(1, viewport.width - padding * 2);
  const availableH = Math.max(1, viewport.height - padding * 2);
  const width = Math.max(1, Number(bounds[2] || 1));
  const height = Math.max(1, Number(bounds[3] || 1));
  let scale = Math.min(availableW / width, availableH / height, Number(maxScale || 1));
  if (!Number.isFinite(scale) || scale <= 0) scale = 1;
  scale = Math.max(0.02, Math.min(scale, Number(ds.max_scale || 10)));

  const centerX = Number(bounds[0]) + width / 2;
  const centerY = Number(bounds[1]) + height / 2;
  ds.scale = scale;
  ds.offset[0] = viewport.width / (2 * scale) - centerX;
  ds.offset[1] = viewport.height / (2 * scale) - centerY;
  app.canvas?.setDirty?.(true, true);
  return true;
}

function screenshotGraphClientBox(bounds) {
  const graphCanvas = screenshotGraphCanvas();
  const ds = app.canvas?.ds;
  const rect = graphCanvas?.getBoundingClientRect?.();
  if (!bounds || !rect || !ds) return null;
  const scale = Number(ds.scale || 1);
  const offsetX = Number(ds.offset?.[0] || 0);
  const offsetY = Number(ds.offset?.[1] || 0);
  if (!Number.isFinite(scale) || scale <= 0) return null;
  return {
    x: rect.x + (Number(bounds[0]) + offsetX) * scale,
    y: rect.y + (Number(bounds[1]) + offsetY) * scale,
    width: Math.max(1, Number(bounds[2]) * scale),
    height: Math.max(1, Number(bounds[3]) * scale),
  };
}

async function preparePlaywrightWorkflowCapture(payload) {
  const workflow = payload?.workflow;
  if (!workflow || !Array.isArray(workflow.nodes)) {
    throw new Error("Playwright capture requires a serialized ComfyUI UI workflow.");
  }
  if (!screenshotCaptureFrontendReady()) {
    throw new Error(
      "ComfyUI frontend setup is not complete; app.canvas/rootGraph are unavailable for real screenshot capture."
    );
  }

  // Let the real ComfyUI frontend configure every installed node and frontend
  // extension. Disable only view restoration and missing-asset scans so they
  // cannot race ComfyUI-Pi's screenshot framing on this disposable capture page.
  await app.loadGraphData(workflow, true, false, null, {
    deferWarnings: true,
    skipAssetScans: true,
    silentAssetErrors: true,
  });
  await screenshotNextPaint(8);

  const mode = String(payload?.mode || "workflow").toLowerCase();
  const nodeCapture = mode === "node" || mode === SCREENSHOT_EXACT_NODE_MODE;
  const padding = mode === "node"
    ? Math.max(SCREENSHOT_MIN_NODE_PADDING, Number(payload?.padding_px || SCREENSHOT_MIN_NODE_PADDING))
    : mode === SCREENSHOT_EXACT_NODE_MODE
      ? 0
      : Math.max(0, Number(payload?.padding_px ?? SCREENSHOT_DEFAULT_WORKFLOW_PADDING));

  let graphNode = null;
  let workflowBounds = null;
  if (nodeCapture) {
    const nodeId = String(payload?.node_id || "");
    graphNode = screenshotFindGraphNode(nodeId);
    if (!graphNode?.pos || !graphNode?.size) {
      throw new Error(`Workflow node ${nodeId} does not exist or has no position/size.`);
    }
    // Exact-node capture still centers the real node comfortably in the Playwright
    // viewport, but only the measured Vue node DOM box is written to the PNG.
    const fitPadding = mode === SCREENSHOT_EXACT_NODE_MODE ? 80 : padding;
    screenshotFitBounds(
      [
        Number(graphNode.pos[0]),
        Number(graphNode.pos[1]),
        Number(graphNode.size[0]),
        Number(graphNode.size[1]),
      ],
      fitPadding,
      mode === SCREENSHOT_EXACT_NODE_MODE ? 1.0 : 1.5,
    );
  } else {
    workflowBounds = screenshotGraphBounds();
    if (!workflowBounds) throw new Error("The workflow has no nodes to capture.");
    screenshotFitBounds(workflowBounds, Math.max(40, padding), 1.0);
  }

  await screenshotNextPaint(8);
  const graphCanvas = screenshotGraphCanvas();
  const canvasRect = graphCanvas?.getBoundingClientRect?.();
  return {
    mode,
    node_id: String(payload?.node_id || ""),
    node_type: String(graphNode?.type || payload?.node_type || ""),
    node_count: screenshotGraphNodes().length,
    workflow_box: workflowBounds ? screenshotGraphClientBox(workflowBounds) : null,
    canvas: canvasRect ? {
      x: canvasRect.x,
      y: canvasRect.y,
      width: canvasRect.width,
      height: canvasRect.height,
    } : null,
  };
}

function screenshotStorageSnapshot(storage) {
  const result = {};
  try {
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key != null) result[key] = storage.getItem(key);
    }
  } catch {}
  return result;
}

async function completeLiveScreenshotRequest(request) {
  const requestId = String(request?.request_id || "");
  if (!requestId) return;
  const endpoint = `/pi-agent/screenshot/complete/${encodeURIComponent(requestId)}`;
  try {
    const captureRequest = { ...request };
    let workflow = request?.workflow;
    delete captureRequest.workflow;

    if (!workflow && String(request?.mode || "") === SCREENSHOT_EXACT_NODE_MODE &&
        String(request?.node_type || "") && !String(request?.node_id || "")) {
      workflow = screenshotInstalledNodeWorkflow(request.node_type);
      captureRequest.node_id = "1";
    }
    if (!workflow) workflow = currentWorkflow();
    if (!workflow || !Array.isArray(workflow.nodes)) {
      throw new Error("No serialized ComfyUI workflow is available for the requested capture.");
    }

    const response = await api.fetchApi("/pi-agent/screenshot/playwright", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request: captureRequest,
        workflow,
        viewport: {
          width: Math.max(800, Number(window.innerWidth || 0)),
          height: Math.max(600, Number(window.innerHeight || 0)),
        },
        local_storage: screenshotStorageSnapshot(window.localStorage),
        session_storage: screenshotStorageSnapshot(window.sessionStorage),
        prefers_dark: Boolean(window.matchMedia?.("(prefers-color-scheme: dark)")?.matches),
      }),
    });
    if (!response.ok) {
      let message = `Playwright screenshot failed: HTTP ${response.status}`;
      try {
        const data = await response.json();
        message = String(data?.error || message);
      } catch {}
      throw new Error(message);
    }

    const blob = await response.blob();
    const query = new URLSearchParams({
      width: String(response.headers.get("X-ComfyUI-Pi-Width") || 0),
      height: String(response.headers.get("X-ComfyUI-Pi-Height") || 0),
      mode: String(response.headers.get("X-ComfyUI-Pi-Mode") || captureRequest.mode || ""),
      node_id: String(response.headers.get("X-ComfyUI-Pi-Node-Id") || captureRequest.node_id || ""),
      node_type: String(response.headers.get("X-ComfyUI-Pi-Node-Type") || captureRequest.node_type || ""),
      padding_px: String(response.headers.get("X-ComfyUI-Pi-Padding") || captureRequest.padding_px || 0),
      node_width_px: String(response.headers.get("X-ComfyUI-Pi-Node-Width") || 0),
      node_height_px: String(response.headers.get("X-ComfyUI-Pi-Node-Height") || 0),
      capture_backend: String(response.headers.get("X-ComfyUI-Pi-Capture-Backend") || ""),
    });
    const completed = await api.fetchApi(`${endpoint}?${query.toString()}`, {
      method: "POST",
      headers: { "Content-Type": "image/png" },
      body: blob,
    });
    if (!completed.ok) throw new Error(`Screenshot upload failed: ${completed.status}`);
  } catch (error) {
    try {
      await api.fetchApi(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ok: false, error: String(error) }),
      });
    } catch {}
  }
}

function startWorkflowScreenshotWorker() {
  if (SCREENSHOT_WORKER_TIMER) return;
  const tick = async () => {
    if (SCREENSHOT_WORKER_BUSY) return;
    SCREENSHOT_WORKER_BUSY = true;
    try {
      const data = await fetchJson("/pi-agent/screenshot/pending");
      if (data?.request) await completeLiveScreenshotRequest(data.request);
    } catch {
      // The worker only supplies the current workflow snapshot. Playwright owns capture.
    } finally {
      SCREENSHOT_WORKER_BUSY = false;
    }
  };
  tick();
  SCREENSHOT_WORKER_TIMER = setInterval(tick, 900);
}

function extensionAssetUrl(relativePath) {
  return new URL(relativePath, import.meta.url).href;
}

function loadExternalScript(src, id) {
  if (id && document.getElementById(id)) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    if (id) script.id = id;
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Unable to load terminal asset: ${src}`));
    document.head.appendChild(script);
  });
}

async function ensureTerminalAssets() {
  if (window.Terminal && window.fit) return;
  if (CHAT_STATE.terminalAssetsPromise) return CHAT_STATE.terminalAssetsPromise;
  CHAT_STATE.terminalAssetsPromise = (async () => {
    if (!document.getElementById("pi-agent-xterm-css")) {
      const link = document.createElement("link");
      link.id = "pi-agent-xterm-css";
      link.rel = "stylesheet";
      link.href = extensionAssetUrl("./vendor/xterm.css");
      document.head.appendChild(link);
    }
    await loadExternalScript(extensionAssetUrl("./vendor/xterm.js"), "pi-agent-xterm-js");
    await loadExternalScript(extensionAssetUrl("./vendor/xterm-fit.js"), "pi-agent-xterm-fit-js");
    if (!window.Terminal) throw new Error("xterm.js did not initialize.");
    if (window.fit?.apply) window.fit.apply(window.Terminal);
  })();
  return CHAT_STATE.terminalAssetsPromise;
}

function terminalWebSocketUrl(sessionId) {
  const basePath = `/pi-agent/terminal/ws/${encodeURIComponent(sessionId)}`;
  let httpUrl;
  try {
    httpUrl = typeof api.apiURL === "function" ? api.apiURL(basePath) : basePath;
  } catch {
    httpUrl = basePath;
  }
  const url = new URL(httpUrl, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function normalizePiTerminalOutput(data) {
  // Pi's current TUI wraps redraws in DEC synchronized-output mode (2026).
  // The bundled xterm renderer predates that mode. Unknown DEC modes should be
  // ignored, but stripping only the begin/end wrappers avoids old-renderer blank
  // redraws while leaving all visible ANSI content untouched.
  return String(data || "").replace(/\x1b\[\?2026[hl]/g, "");
}

function closeTerminalSocket() {
  const ws = CHAT_STATE.terminalSocket;
  CHAT_STATE.terminalSocket = null;
  if (ws) {
    try { ws.close(); } catch {}
  }
}

async function stopTerminalForSessionChange(sessionId) {
  const previous = String(sessionId || "").trim();
  closeTerminalSocket();
  CHAT_STATE.terminalRecoveryAttempts = 0;
  CHAT_STATE.terminal?.reset();
  if (!previous) return;
  try {
    await fetchJson("/pi-agent/terminal/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: previous }),
    });
  } catch {
    // Session switching must still rebind the browser even if the old PTY is already gone.
  }
}

function terminalNotifyPtySize(term) {
  const ws = CHAT_STATE.terminalSocket;
  if (!term || ws?.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({
    type: "resize",
    cols: Math.max(20, Number(term.cols || 100)),
    rows: Math.max(6, Number(term.rows || 32)),
  }));
}

function terminalCellGeometry(term) {
  const legacy = term?.renderer?.dimensions;
  const legacyWidth = Number(legacy?.actualCellWidth || 0);
  const legacyHeight = Number(legacy?.actualCellHeight || 0);
  if (legacyWidth > 0 && legacyHeight > 0) {
    return { width: legacyWidth, height: legacyHeight };
  }

  const modern = term?._core?._renderService?.dimensions?.css?.cell;
  const modernWidth = Number(modern?.width || 0);
  const modernHeight = Number(modern?.height || 0);
  if (modernWidth > 0 && modernHeight > 0) {
    return { width: modernWidth, height: modernHeight };
  }

  const row = term?.element?.querySelector?.(".xterm-rows > div");
  const rowRect = row?.getBoundingClientRect?.();
  const span = row?.querySelector?.("span");
  const spanRect = span?.getBoundingClientRect?.();
  const width = Number(spanRect?.width || 0);
  const height = Number(rowRect?.height || 0);
  if (width > 0 && height > 0) {
    return { width, height };
  }
  return null;
}

function terminalScrollbarWidth(term) {
  const viewport = term?.element?.querySelector?.(".xterm-viewport");
  if (viewport) {
    const width = Math.max(0, Number(viewport.offsetWidth || 0) - Number(viewport.clientWidth || 0));
    if (width > 0) return width;
  }
  return Math.max(0, Number(term?.viewport?.scrollBarWidth || 0));
}

function repaintTerminal(term) {
  if (!term) return false;
  term._comfyPiNeedsRepaint = true;
  const element = term.element;
  if (!element || !element.isConnected || Number(term.rows || 0) <= 0) return false;
  const rect = element.getBoundingClientRect?.();
  if (!rect || rect.width < 20 || rect.height < 20) return false;
  try {
    if (typeof term.refresh === "function") term.refresh(0, term.rows - 1);
    term._comfyPiNeedsRepaint = false;
    return true;
  } catch {
    return false;
  }
}

function scheduleTerminalRepaint(term, ui, { focus = false } = {}) {
  if (!term) return;
  term._comfyPiNeedsRepaint = true;
  term._comfyPiRepaintFocus = Boolean(term._comfyPiRepaintFocus || focus);
  if (term._comfyPiRepaintFrame) return;
  term._comfyPiRepaintFrame = requestAnimationFrame(() => {
    term._comfyPiRepaintFrame = null;
    const shouldFocus = Boolean(term._comfyPiRepaintFocus);
    term._comfyPiRepaintFocus = false;
    repaintTerminal(term);
    if (shouldFocus && term.element?.isConnected && !ui?.terminalPane?.hidden) term.focus();
  });
}

function writeTerminalOutput(term, ui, data) {
  if (!term) return;
  term._comfyPiNeedsRepaint = true;
  const normalized = normalizePiTerminalOutput(data);
  try {
    term.write(normalized, () => scheduleTerminalRepaint(term, ui));
  } catch (error) {
    console.warn("ComfyUI-Pi terminal write failed", error);
  }
  // The bundled legacy xterm renderer may not invoke write callbacks reliably after
  // a DOM detach/reattach. A coalesced animation-frame repaint is a safe fallback;
  // the callback schedules another repaint after parsing when it is supported.
  scheduleTerminalRepaint(term, ui);
}

function resizeTerminalToElement(term) {
  const element = term?.element;
  if (!term || !element || !element.isConnected) {
    if (term) term._comfyPiNeedsRepaint = true;
    return false;
  }

  const rect = element.getBoundingClientRect();
  if (rect.width < 20 || rect.height < 20) {
    term._comfyPiNeedsRepaint = true;
    return false;
  }

  const cell = terminalCellGeometry(term);
  if (!cell) {
    if (typeof term.fit === "function") term.fit();
    repaintTerminal(term);
    return true;
  }

  const style = getComputedStyle(element);
  const paddingX =
    Number.parseFloat(style.paddingLeft || "0") +
    Number.parseFloat(style.paddingRight || "0");
  const paddingY =
    Number.parseFloat(style.paddingTop || "0") +
    Number.parseFloat(style.paddingBottom || "0");
  const availableWidth = Math.max(1, rect.width - paddingX - terminalScrollbarWidth(term));
  const availableHeight = Math.max(1, rect.height - paddingY);
  const cols = Math.max(20, Math.floor(availableWidth / cell.width));
  const rows = Math.max(6, Math.floor(availableHeight / cell.height));

  if (Number(term.cols) !== cols || Number(term.rows) !== rows) {
    term.resize(cols, rows);
  }
  repaintTerminal(term);
  return true;
}

function fitTerminalToHost(term, ui, { notifyPty = true, focus = false } = {}) {
  if (!term || !ui?.terminalHost || ui.terminalPane?.hidden) {
    if (term) term._comfyPiNeedsRepaint = true;
    return false;
  }
  const hostRect = ui.terminalHost.getBoundingClientRect();
  if (hostRect.width < 20 || hostRect.height < 20) {
    term._comfyPiNeedsRepaint = true;
    return false;
  }

  // Bypass the bundled legacy fit addon's parent-computed-height path. Size the
  // actual rendered terminal element directly so xterm rows fill the flex host.
  const resized = resizeTerminalToElement(term);
  if (notifyPty) terminalNotifyPtySize(term);
  if (focus) term.focus();
  return resized;
}

function scheduleTerminalFit(term, ui, { notifyPty = true, focus = false } = {}) {
  if (!term) return;
  if (term._comfyPiFitFrame) {
    try { cancelAnimationFrame(term._comfyPiFitFrame); } catch {}
    term._comfyPiFitFrame = null;
  }
  if (term._comfyPiFitTimer) {
    clearTimeout(term._comfyPiFitTimer);
    term._comfyPiFitTimer = null;
  }

  // Wait through two paints for ComfyUI's sidebar/grid/flex sizing, then run one short
  // delayed verification pass. The last pass always re-sends rows/cols to the PTY so
  // Pi redraws its own footer at the true bottom of the expanded xterm.
  term._comfyPiFitFrame = requestAnimationFrame(() => {
    term._comfyPiFitFrame = requestAnimationFrame(() => {
      term._comfyPiFitFrame = null;
      fitTerminalToHost(term, ui, { notifyPty, focus: false });
      repaintTerminal(term);
      term._comfyPiFitTimer = setTimeout(() => {
        term._comfyPiFitTimer = null;
        fitTerminalToHost(term, ui, { notifyPty, focus });
        repaintTerminal(term);
      }, 90);
    });
  });
}

function detachPiInterface() {
  // ComfyUI destroys a sidebar/bottom-panel renderer when the panel is collapsed.
  // Keep the xterm instance and its WebSocket alive so Pi continues rendering into
  // the detached terminal and can be re-parented with its exact screen/scrollback
  // when the panel is opened again.  Only DOM-host-specific observers/listeners are
  // detached here. Explicit session changes still stop/reset Pi through their APIs.
  if (CHAT_STATE.terminalStatusTimer) {
    clearInterval(CHAT_STATE.terminalStatusTimer);
    CHAT_STATE.terminalStatusTimer = null;
  }
  const term = CHAT_STATE.terminal;
  if (term?._comfyPiResizeObserver) {
    try { term._comfyPiResizeObserver.disconnect(); } catch {}
    term._comfyPiResizeObserver = null;
  }
  if (term?._comfyPiFitFrame) {
    try { cancelAnimationFrame(term._comfyPiFitFrame); } catch {}
    term._comfyPiFitFrame = null;
  }
  if (term?._comfyPiFitTimer) {
    clearTimeout(term._comfyPiFitTimer);
    term._comfyPiFitTimer = null;
  }
  if (term?._comfyPiRepaintFrame) {
    try { cancelAnimationFrame(term._comfyPiRepaintFrame); } catch {}
    term._comfyPiRepaintFrame = null;
  }
  if (term) term._comfyPiNeedsRepaint = true;
  if (term) term._comfyPiRepaintFocus = false;
  try { term?._comfyPiClipboardCleanup?.(); } catch {}
  try { term?._comfyPiPointerCleanup?.(); } catch {}
}

function attachTerminalHost(term, ui) {
  if (!term) return;
  try { term._comfyPiClipboardCleanup?.(); } catch {}
  try { term._comfyPiPointerCleanup?.(); } catch {}
  if (term._comfyPiResizeObserver) {
    try { term._comfyPiResizeObserver.disconnect(); } catch {}
    term._comfyPiResizeObserver = null;
  }

  // xterm can keep running while its former ComfyUI panel is detached. Re-parent
  // the existing terminal DOM instead of constructing a new terminal and replaying
  // the entire PTY byte history on every collapse/expand cycle.
  if (term.element && term.element.parentElement !== ui.terminalHost) {
    ui.terminalHost.appendChild(term.element);
  }
  term._comfyPiNeedsRepaint = true;

  const copyTerminalSelection = term._comfyPiCopyTerminalSelection;
  const pasteTerminalClipboard = term._comfyPiPasteTerminalClipboard;
  if (copyTerminalSelection) ui.terminalHost.addEventListener("keydown", copyTerminalSelection, true);
  if (pasteTerminalClipboard) ui.terminalHost.addEventListener("paste", pasteTerminalClipboard, true);
  term._comfyPiClipboardCleanup = () => {
    if (copyTerminalSelection) ui.terminalHost.removeEventListener("keydown", copyTerminalSelection, true);
    if (pasteTerminalClipboard) ui.terminalHost.removeEventListener("paste", pasteTerminalClipboard, true);
  };

  const pointerdown = () => queueMicrotask(() => term.focus());
  ui.terminalHost.addEventListener("pointerdown", pointerdown);
  term._comfyPiPointerCleanup = () => ui.terminalHost.removeEventListener("pointerdown", pointerdown);

  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => {
      scheduleTerminalFit(term, ui, { notifyPty: true });
    });
    observer.observe(ui.terminalHost);
    observer.observe(ui.terminalPane);
    term._comfyPiResizeObserver = observer;
  }
  scheduleTerminalFit(term, ui, { notifyPty: true });
}

function ensureTerminalInstance(ui) {
  if (CHAT_STATE.terminal) {
    attachTerminalHost(CHAT_STATE.terminal, ui);
    return CHAT_STATE.terminal;
  }
  const term = new window.Terminal({
    cursorBlink: true,
    scrollback: 8000,
    convertEol: false,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    fontSize: 13,
    theme: {
      background: "#0f1115",
      foreground: "#e6e8ec",
      cursor: "#f2f2f2",
      selection: "rgba(90,140,255,0.35)",
    },
  });
  term.open(ui.terminalHost);
  if (typeof term.fit === "function") term.fit();
  const sendTerminalInput = (data) => {
    const ws = CHAT_STATE.terminalSocket;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "input", data }));
  };
  const sendTerminalResize = ({ cols, rows }) => {
    const ws = CHAT_STATE.terminalSocket;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "resize", cols, rows }));
  };
  // xterm 5+ uses onData/onResize disposables. Keep the legacy EventEmitter
  // fallback for the bundled build so terminal input works across ComfyUI installs.
  term._comfyPiDataDisposable = typeof term.onData === "function"
    ? term.onData(sendTerminalInput)
    : term.on("data", sendTerminalInput);
  term._comfyPiResizeDisposable = typeof term.onResize === "function"
    ? term.onResize(sendTerminalResize)
    : term.on("resize", sendTerminalResize);

  // Match normal desktop-terminal clipboard behavior without stealing Pi's Ctrl+C
  // interrupt. Ctrl/Cmd+C copies only when xterm has a selection; otherwise the
  // keystroke continues to Pi. Text paste is forwarded directly to the PTY.
  const copyTerminalSelection = (event) => {
    const key = String(event.key || "").toLowerCase();
    if (!(event.ctrlKey || event.metaKey) || event.altKey || key !== "c") return;
    const selection = typeof term.getSelection === "function" ? term.getSelection() : "";
    if (!selection) return;
    event.preventDefault();
    event.stopPropagation();
    Promise.resolve(copyText(selection)).catch(() => {});
  };
  const pasteTerminalClipboard = (event) => {
    const text = event.clipboardData?.getData("text/plain") || "";
    if (!text) return;
    event.preventDefault();
    event.stopPropagation();
    if (typeof term.paste === "function") term.paste(text);
    else sendTerminalInput(text);
  };
  term._comfyPiCopyTerminalSelection = copyTerminalSelection;
  term._comfyPiPasteTerminalClipboard = pasteTerminalClipboard;
  CHAT_STATE.terminal = term;
  attachTerminalHost(term, ui);
  return term;
}

function terminalDimensions(ui) {
  const term = CHAT_STATE.terminal;
  if (term) return { cols: term.cols || 100, rows: term.rows || 32 };
  return { cols: 100, rows: 32 };
}

async function connectTerminalSocket(ui) {
  const sessionId = CHAT_STATE.sessionId;
  if (!sessionId) return;
  closeTerminalSocket();
  const ws = new WebSocket(terminalWebSocketUrl(sessionId));
  ws._comfyPiSessionId = sessionId;
  CHAT_STATE.terminalSocket = ws;
  ws.addEventListener("open", () => {
    if (CHAT_STATE.terminalSocket !== ws || CHAT_STATE.sessionId !== sessionId) {
      try { ws.close(); } catch {}
      return;
    }
    CHAT_STATE.terminalRecoveryAttempts = 0;
    ui.terminalStatus.textContent = "Connected to Pi terminal.";
    const term = CHAT_STATE.terminal;
    if (term) {
      if (ui.includeWorkflow.checked) ws.send(JSON.stringify({ type: "workflow", workflow: currentWorkflow() }));
      scheduleTerminalFit(term, ui, { notifyPty: true, focus: true });
    }
  });
  ws.addEventListener("message", (event) => {
    if (CHAT_STATE.terminalSocket !== ws || CHAT_STATE.sessionId !== sessionId) return;
    let payload;
    try { payload = JSON.parse(event.data); } catch { payload = { type: "output", data: String(event.data || "") }; }
    if (payload.type === "output") {
      writeTerminalOutput(CHAT_STATE.terminal, ui, payload.data);
    }
    if (payload.type === "exit") {
      const code = payload.status?.exit_code;
      const resumable = Boolean(payload.status?.resumable);
      ui.terminalStatus.textContent = resumable
        ? `Pi terminal exited${code == null ? "" : ` with code ${code}`}; automatically resuming saved session…`
        : `Pi terminal exited${code == null ? "" : ` with code ${code}`}.`;
      if (resumable && CHAT_STATE.terminalRecoveryAttempts < 3) {
        CHAT_STATE.terminalRecoveryAttempts += 1;
        const recoverySession = CHAT_STATE.sessionId;
        closeTerminalSocket();
        setTimeout(() => {
          if (CHAT_STATE.sessionId === recoverySession && CHAT_STATE.view === "terminal") {
            startTerminal(ui);
          }
        }, 300 * CHAT_STATE.terminalRecoveryAttempts);
      }
    }
  });
  ws.addEventListener("close", () => {
    if (CHAT_STATE.terminalSocket === ws) CHAT_STATE.terminalSocket = null;
  });
  ws.addEventListener("error", () => {
    if (CHAT_STATE.terminalSocket === ws && CHAT_STATE.sessionId === sessionId) {
      ui.terminalStatus.textContent = "Pi terminal connection error.";
    }
  });
}

function terminalStartPayload(ui, { resume = false } = {}) {
  const dims = terminalDimensions(ui);
  return {
    session_id: CHAT_STATE.sessionId,
    project_directory: ui.project.value.trim(),
    ...selectedProviderPayload(ui),
    scoped_models: ui.scopedModels.value.trim(),
    pi_executable: ui.executable.value.trim(),
    timeout_seconds: Number(ui.timeout.value || 180),
    cols: dims.cols,
    rows: dims.rows,
    resume,
    workflow: ui.includeWorkflow.checked ? currentWorkflow() : null,
    project_context: ui.projectContext.value.trim(),
    preemptive_handoff: ui.preemptiveHandoff.checked,
    handoff_threshold_percent: Number(ui.handoffThreshold.value || 82.5),
    handoff_max_chars: Number(ui.handoffMaxChars.value || 8000),
  };
}

async function startTerminal(ui, { restart = false } = {}) {
  if (!CHAT_STATE.terminalSupported || CHAT_STATE.terminalStarting) return;
  if (!CHAT_STATE.sessionId) {
    const session = await createSession(ui);
    await refreshSessions(ui, session.session_id);
  }
  if (CHAT_STATE.modelPreparationPromise) await CHAT_STATE.modelPreparationPromise;
  CHAT_STATE.terminalStarting = true;
  ui.terminalStatus.textContent = restart ? "Restarting Pi terminal with selected model…" : "Starting real Pi terminal…";
  try {
    await ensureTerminalAssets();
    ensureTerminalInstance(ui);

    // A live socket is reusable only when it belongs to the currently selected
    // ComfyUI-Pi session. Session changes must never inherit another session's PTY.
    if (CHAT_STATE.terminalSocket &&
        CHAT_STATE.terminalSocket._comfyPiSessionId !== CHAT_STATE.sessionId) {
      closeTerminalSocket();
    }

    // A normal panel collapse does not close the live WebSocket anymore. If it is
    // still open for this exact session, the detached xterm has continued receiving
    // Pi output, so reopening is just a DOM re-parent + fit operation.
    if (!restart &&
        CHAT_STATE.terminalSocket?.readyState === WebSocket.OPEN &&
        CHAT_STATE.terminalSocket._comfyPiSessionId === CHAT_STATE.sessionId) {
      ui.terminalStatus.textContent = "Connected to Pi terminal.";
      scheduleTerminalFit(CHAT_STATE.terminal, ui, { notifyPty: true, focus: true });
      return;
    }

    // The socket may have dropped while the panel was hidden or after a browser-side
    // remount. Ask the cheap terminal-status endpoint first. A live backend PTY can be
    // reattached directly; do not call /terminal/start because that route may include
    // llama.cpp readiness checks intended only for an actual process start.
    let resumeSaved = false;
    if (!restart) {
      try {
        const status = await fetchJson(`/pi-agent/terminal/status/${encodeURIComponent(CHAT_STATE.sessionId)}`);
        if (status.running || status.recovering) {
          ui.terminalStatus.textContent = status.recovering
            ? (status.message || "Pi is automatically resuming the saved session…")
            : "Reconnecting to existing Pi terminal…";
          CHAT_STATE.terminal?.reset();
          await connectTerminalSocket(ui);
          return;
        }
        resumeSaved = Boolean(status.resumable);
      } catch {}
    }

    const endpoint = restart ? "/pi-agent/terminal/restart" : "/pi-agent/terminal/start";
    await fetchJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(terminalStartPayload(ui, { resume: restart || resumeSaved })),
    });
    CHAT_STATE.terminal?.reset();
    await connectTerminalSocket(ui);
  } catch (error) {
    ui.terminalStatus.textContent = String(error);
    // Stay in Terminal view even when Pi is stopped. New session and the session
    // dropdown must remain usable, and reopening Terminal can retry a saved session.
  } finally {
    CHAT_STATE.terminalStarting = false;
  }
}

async function restartTerminalIfActive(ui) {
  if (CHAT_STATE.view !== "terminal" || !CHAT_STATE.terminalSupported || !CHAT_STATE.sessionId) return;
  try {
    const status = await fetchJson(`/pi-agent/terminal/status/${encodeURIComponent(CHAT_STATE.sessionId)}`);
    await startTerminal(ui, { restart: Boolean(status.running) });
  } catch (error) {
    ui.terminalStatus.textContent = String(error);
  }
}

function switchView(ui, view) {
  const requested = view === "chat" ? "chat" : "terminal";
  const target = requested === "terminal" && ui.terminalTab.getAttribute("aria-disabled") === "true"
    ? "chat"
    : requested;
  CHAT_STATE.view = target;
  sessionStorage.setItem("ComfyUIPi.ActiveView", target);
  ui.terminalPane.hidden = target !== "terminal";
  ui.chatPane.hidden = target !== "chat";
  ui.terminalTab.classList.toggle("active", target === "terminal");
  ui.chatTab.classList.toggle("active", target === "chat");
  ui.terminalTab.setAttribute("aria-selected", String(target === "terminal"));
  ui.chatTab.setAttribute("aria-selected", String(target === "chat"));
  ui.chatActions.hidden = target !== "chat";
  if (target === "terminal") {
    startTerminal(ui).then(() => {
      scheduleTerminalFit(CHAT_STATE.terminal, ui, { notifyPty: true, focus: true });
    });
  } else {
    ui.textarea.focus();
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
    .pi-agent-interface-root { height:100%; min-height:0; width:100%; display:flex; flex-direction:column; overflow:hidden; }
    .pi-agent-interface-root > .pi-agent-shell { flex:1 1 0; height:auto; min-height:0; width:100%; overflow:hidden; }
    .pi-agent-shell { height: 100%; min-height: 0; display: flex; flex-direction: column; color: var(--fg-color, inherit); background: var(--comfy-menu-bg, transparent); }
    .pi-agent-toolbar { display:flex; align-items:center; gap:6px; padding:8px; border-bottom:1px solid color-mix(in srgb, currentColor 15%, transparent); flex-wrap:wrap; }
    .pi-agent-title { font-weight:600; margin-right:auto; }
    .pi-agent-pill { font-size:11px; padding:2px 7px; border-radius:999px; border:1px solid color-mix(in srgb, currentColor 20%, transparent); opacity:.9; }
    .pi-agent-btn { border:1px solid color-mix(in srgb, currentColor 22%, transparent); background:color-mix(in srgb, currentColor 6%, transparent); color:inherit; border-radius:7px; padding:6px 9px; cursor:pointer; font:inherit; }
    .pi-agent-btn:hover { background:color-mix(in srgb, currentColor 11%, transparent); }
    .pi-agent-btn:disabled { opacity:.45; cursor:not-allowed; }
    .pi-agent-icon-btn { width:32px; height:32px; display:inline-grid; place-items:center; padding:0; line-height:1; font-size:17px; border-radius:7px; }
    .pi-agent-icon-btn .pi { font-size:16px; pointer-events:none; }
    .pi-agent-session-toolbar { flex-wrap:nowrap; }
    .pi-agent-sessions { min-width:0; max-width:none; flex:1 1 auto; border:1px solid color-mix(in srgb, currentColor 22%, transparent); background:var(--comfy-menu-bg, inherit); color:inherit; border-radius:7px; padding:5px 7px; }
    .pi-agent-session-actions { display:flex; align-items:center; gap:4px; flex:0 0 auto; }
    .pi-agent-session-actions .pi-agent-icon-btn { width:30px; height:30px; font-size:15px; }
    .pi-agent-emoji-icon { font-size:16px; line-height:1; pointer-events:none; }
    .pi-agent-settings { padding:8px; border-bottom:1px solid color-mix(in srgb, currentColor 15%, transparent); display:grid; gap:7px; flex:0 1 auto; min-height:0; overflow-y:auto; overflow-x:hidden; overscroll-behavior:contain; scrollbar-gutter:stable; }
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
    .pi-agent-composer-actions { display:flex; gap:7px; align-items:center; justify-content:flex-end; padding:0 8px 8px; }
    .pi-agent-composer-actions[hidden] { display:none !important; }
    .pi-agent-help { font-size:10px; opacity:.6; }
    .pi-agent-statusline { font-size:11px; min-height:16px; padding:0 2px; opacity:.72; }
    .pi-agent-statusline:empty { display:none; }
    .pi-agent-command-menu { display:none; max-height:220px; overflow:auto; border:1px solid color-mix(in srgb, currentColor 22%, transparent); border-radius:8px; background:var(--comfy-menu-bg, #222); }
    .pi-agent-command-menu.open { display:block; }
    .pi-agent-command-item { padding:7px 9px; cursor:pointer; display:grid; gap:2px; }
    .pi-agent-command-item.active, .pi-agent-command-item:hover { background:color-mix(in srgb, currentColor 10%, transparent); }
    .pi-agent-command-name { font-family:monospace; font-size:12px; }
    .pi-agent-command-desc { font-size:10px; opacity:.68; }
    .pi-agent-local-box { border:1px solid color-mix(in srgb, currentColor 16%, transparent); border-radius:8px; padding:8px; display:grid; gap:7px; }
    .pi-agent-local-actions { display:flex; gap:6px; flex-wrap:wrap; }
    .pi-agent-local-status { font-size:10px; opacity:.72; white-space:pre-wrap; }
    .pi-agent-view-tabs { display:flex; gap:0; padding:0 8px; border-bottom:1px solid color-mix(in srgb, currentColor 15%, transparent); }
    .pi-agent-view-tab { position:relative; padding:8px 14px 7px; cursor:pointer; opacity:.7; user-select:none; border-bottom:2px solid transparent; margin-bottom:-1px; }
    .pi-agent-view-tab:hover { opacity:1; background:color-mix(in srgb, currentColor 6%, transparent); }
    .pi-agent-view-tab:focus-visible { outline:1px solid color-mix(in srgb, #4f8cff 70%, white 10%); outline-offset:-2px; }
    .pi-agent-view-tab.active { opacity:1; font-weight:600; border-bottom-color:#4f8cff; background:transparent; }
    .pi-agent-view-tab[aria-disabled="true"] { opacity:.35; cursor:not-allowed; pointer-events:none; }
    .pi-agent-terminal-pane { flex:1 1 0; min-height:0; display:flex; flex-direction:column; overflow:hidden; background:#0f1115; }
    .pi-agent-terminal-pane[hidden], .pi-agent-chat-pane[hidden] { display:none !important; }
    .pi-agent-terminal-host { flex:1 1 0; min-height:0; width:100%; overflow:hidden; padding:4px; box-sizing:border-box; background:#0f1115; }
    .pi-agent-terminal-host .terminal { height:100%; }
    .pi-agent-terminal-status { font-size:10px; padding:4px 8px; min-height:16px; border-top:1px solid #2a2d34; color:#c8ccd4; background:#15181e; }
    .pi-agent-terminal-host .xterm, .pi-agent-terminal-host .xterm-viewport, .pi-agent-terminal-host .xterm-screen { height:100%; }
    .pi-agent-terminal-host .xterm-helper-textarea { pointer-events:auto; }
    .pi-agent-shell.pi-agent-placement-bottom { height:100%; min-height:220px; width:100%; }
    .pi-agent-shell.pi-agent-placement-bottom .pi-agent-terminal-pane, .pi-agent-shell.pi-agent-placement-bottom .pi-agent-terminal-host { min-height:150px; }
    .pi-agent-shell.pi-agent-placement-bottom .pi-agent-messages { min-height:120px; }
    .pi-agent-chat-pane { flex:1 1 auto; min-height:0; display:flex; flex-direction:column; }
    .pi-agent-shared-controls { flex:0 0 auto; border-top:1px solid color-mix(in srgb, currentColor 15%, transparent); padding:6px 8px 8px; display:grid; gap:5px; }
    .pi-agent-activity-block { margin-top:8px; border-top:1px solid color-mix(in srgb, currentColor 14%, transparent); padding-top:6px; font-size:11px; }
    .pi-agent-activity-block summary { cursor:pointer; font-weight:600; opacity:.8; }
    .pi-agent-activity-block pre { max-height:280px; overflow:auto; white-space:pre-wrap; margin:6px 0 0; padding:7px; border-radius:6px; background:color-mix(in srgb, currentColor 7%, transparent); }
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

  row.appendChild(content);

  const reasoning = String(message.reasoning || "").trim();
  if (reasoning && CHAT_STATE.showReasoning) {
    const details = document.createElement("details");
    details.className = "pi-agent-activity-block pi-agent-reasoning-block";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = "Reasoning";
    const body = document.createElement("pre");
    body.textContent = reasoning;
    details.append(summary, body);
    row.appendChild(details);
  }

  const activity = Array.isArray(message.activity) ? message.activity : [];
  if (activity.length && CHAT_STATE.showTools) {
    const details = document.createElement("details");
    details.className = "pi-agent-activity-block pi-agent-tools-block";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = `Tools / activity (${activity.length})`;
    const body = document.createElement("pre");
    body.textContent = activity.map((item) => {
      const type = String(item?.type || "tool");
      const name = String(item?.name || "tool");
      const payload = item?.result ?? item?.arguments ?? "";
      let suffix = "";
      if (payload !== "" && payload != null) {
        try { suffix = `\n${JSON.stringify(payload, null, 2)}`; } catch { suffix = `\n${String(payload)}`; }
      }
      return `${type}: ${name}${suffix}`;
    }).join("\n\n").slice(0, 30000);
    details.append(summary, body);
    row.appendChild(details);
  }

  row.appendChild(meta);
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
  const handoffInfo = count ? ` Checkpoints: ${count}. Last: ${last.path || "saved"}.` : "";
  ui.contextPill.title = `In-place compaction threshold ${(threshold * 100).toFixed(1)}%.${handoffInfo}`;
}

async function loadSession(ui, sessionId) {
  const data = await fetchJson(`/pi-agent/chat/session/${encodeURIComponent(sessionId)}`);
  const nextSessionId = String(data.session?.session_id || "").trim();
  if (!nextSessionId) throw new Error("Loaded session did not return a session id.");
  const previous = CHAT_STATE.sessionId;
  if (previous && previous !== nextSessionId) {
    await stopTerminalForSessionChange(previous);
  }
  rememberSessionId(nextSessionId);
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
    const endpoint = String(local.base_url || defaultEndpoint || "");
    const savedModelCount = Array.isArray(local.models) ? local.models.length : (sessionModel ? 1 : 0);
    ui.localStatus.textContent = `Endpoint: ${endpoint}\n${savedModelCount} saved model(s). Use Refresh models / apply endpoint to re-probe the host.`;
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
  if (target && !CHAT_STATE.sessions.some((session) => session.session_id === target)) target = null;
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
  const nextSessionId = String(data.session?.session_id || "").trim();
  if (!nextSessionId) throw new Error("New session did not return a session id.");
  const previous = CHAT_STATE.sessionId;
  if (previous && previous !== nextSessionId) {
    await stopTerminalForSessionChange(previous);
  }
  rememberSessionId(nextSessionId);
  return data.session;
}

function setBusy(ui, busy) {
  CHAT_STATE.busy = busy;
  for (const control of [
    ui.newChat,
    ui.loadSessionButton,
    ui.saveSessionButton,
    ui.renameSessionButton,
    ui.deleteChat,
  ]) {
    if (control) control.disabled = busy;
  }
  ui.sessionSelect.disabled = busy;
  ui.provider.disabled = busy;
  ui.model.disabled = busy || ui.provider.value === "pi-default";
  ui.stop.classList.toggle("pi-agent-hidden", !busy);
  ui.statusline.textContent = busy ? "Pi is working…" : "";
}

async function sendMessage(ui) {
  const message = ui.textarea.value.trim();
  if (!message || CHAT_STATE.busy) return;
  if (CHAT_STATE.modelPreparationPromise) {
    const model = ui.model.value || "selected local model";
    ui.statusline.textContent = `Waiting for ${model} to finish loading before sending…`;
    try {
      await CHAT_STATE.modelPreparationPromise;
    } catch (error) {
      ui.statusline.textContent = String(error);
      return;
    }
  }
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
  if (isLocalProvider(ui.provider.value) && ui.model.value) {
    const configuredTimeout = Number(ui.timeout.value || 180);
    ui.statusline.textContent = `Ensuring ${ui.model.value} is ready before Pi starts (timeout: ${configuredTimeout}s)…`;
  }

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
        ui.statusline.textContent = data.handoff.continuity_method === "pi_compaction"
          ? "Durable checkpoint saved; Pi compacted the current session in place."
          : "Durable context checkpoint saved.";
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
      await restartTerminalIfActive(ui);
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
      await restartTerminalIfActive(ui);
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
    await restartTerminalIfActive(ui);
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
  const prepare = (async () => {
    ui.model.disabled = true;
    if (isLocalProvider(selector)) {
      const configuredTimeout = Number(ui.timeout.value || 180);
      ui.statusline.textContent = `Preparing ${model}… waiting up to ${configuredTimeout}s for the local host to report it ready.`;
    }
    const data = await persistModelSelection(ui, provider, model);
    ui.statusline.textContent = `Using ${data.provider || provider}/${data.model || model}`;
    if (isLocalProvider(selector)) {
      const endpoint = ui.localBaseUrl.value.trim() || LOCAL_PROVIDER_DEFAULTS[selector] || "";
      ui.localStatus.textContent = `Endpoint: ${endpoint}\n${ui.model.options.length} model(s) reported by this host. Selected model is ready.`;
    }
    await restartTerminalIfActive(ui);
    return data;
  })();
  CHAT_STATE.modelPreparationPromise = prepare;
  try {
    await prepare;
  } catch (error) {
    ui.statusline.textContent = String(error);
  } finally {
    if (CHAT_STATE.modelPreparationPromise === prepare) CHAT_STATE.modelPreparationPromise = null;
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

function sessionFilename(session) {
  const title = String(session?.title || "comfyui-pi-session")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64) || "comfyui-pi-session";
  const suffix = String(session?.session_id || "").slice(0, 8);
  return `${title}${suffix ? `-${suffix}` : ""}.comfyui-pi-session.json`;
}

async function saveSessionFile(ui) {
  if (!CHAT_STATE.sessionId || CHAT_STATE.busy) return;
  const data = await fetchJson(`/pi-agent/chat/session/${encodeURIComponent(CHAT_STATE.sessionId)}`);
  const session = data.session || {};
  const blob = new Blob([`${JSON.stringify(session, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = sessionFilename(session);
    document.body.appendChild(link);
    link.click();
    link.remove();
    ui.statusline.textContent = `Saved session: ${session.title || "Chat"}`;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function loadSessionFile(ui, file) {
  if (!file || CHAT_STATE.busy) return;
  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch (error) {
    ui.statusline.textContent = `Unable to load session JSON: ${String(error)}`;
    return;
  }
  const source = parsed?.session && typeof parsed.session === "object" ? parsed.session : parsed;
  const data = await fetchJson("/pi-agent/chat/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: source }),
  });
  const previous = CHAT_STATE.sessionId;
  const importedId = data.session?.session_id;
  if (!importedId) throw new Error("Imported session did not return a session id.");

  if (previous && previous !== importedId && CHAT_STATE.view === "terminal") {
    try {
      await fetchJson("/pi-agent/terminal/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: previous }),
      });
    } catch {}
  }
  await refreshSessions(ui, importedId);
  await refreshCommandCatalog(ui);
  if (CHAT_STATE.terminal) CHAT_STATE.terminal.reset();
  ui.statusline.textContent = `Loaded session: ${data.session.title || "Chat"}`;
  if (CHAT_STATE.view === "terminal") await startTerminal(ui);
  else ui.textarea.focus();
}

async function renameCurrentSession(ui) {
  if (!CHAT_STATE.sessionId || CHAT_STATE.busy) return;
  const current = CHAT_STATE.sessions.find((item) => item.session_id === CHAT_STATE.sessionId);
  const previousTitle = String(current?.title || "Chat");
  const requested = window.prompt("Rename chat session", previousTitle);
  if (requested == null) return;
  const title = requested.trim();
  if (!title) {
    ui.statusline.textContent = "Session name cannot be empty.";
    return;
  }
  const data = await fetchJson(
    `/pi-agent/chat/session/${encodeURIComponent(CHAT_STATE.sessionId)}/rename`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    },
  );
  const savedTitle = String(data.session?.title || title);
  const option = [...ui.sessionSelect.options].find((item) => item.value === CHAT_STATE.sessionId);
  if (option) option.textContent = savedTitle;
  if (current) current.title = savedTitle;
  ui.statusline.textContent = `Renamed session to: ${savedTitle}`;
}

function buildSidebar(el, placement = "sidebar") {
  ensureStyles();
  el.classList.add("pi-agent-interface-root");
  const placementClass = placement === "bottom" ? "pi-agent-placement-bottom" : "pi-agent-placement-sidebar";
  el.innerHTML = `
    <div class="pi-agent-shell ${placementClass}">
      <div class="pi-agent-toolbar">
        <span class="pi-agent-title">Pi Agent</span>
        <span id="pi-agent-runtime-pill" class="pi-agent-pill">Checking Pi…</span>
        <span id="pi-agent-context-pill" class="pi-agent-pill" title="Context pressure and in-place compaction checkpoint status">Context --</span>
        <button id="pi-agent-settings-toggle" class="pi-agent-btn pi-agent-icon-btn" type="button" title="Pi Agent settings" aria-label="Chat settings"><i class="pi pi-cog" aria-hidden="true"></i></button>
      </div>
      <div class="pi-agent-toolbar pi-agent-session-toolbar">
        <select id="pi-agent-session-select" class="pi-agent-sessions" aria-label="Saved Pi session"></select>
        <div class="pi-agent-session-actions" aria-label="Session actions">
          <button id="pi-agent-new-chat" class="pi-agent-btn pi-agent-icon-btn" type="button" title="New session" aria-label="New session"><i class="pi pi-plus" aria-hidden="true"></i></button>
          <button id="pi-agent-load-session" class="pi-agent-btn pi-agent-icon-btn" type="button" title="Load session JSON" aria-label="Load session JSON"><i class="pi pi-folder-open" aria-hidden="true"></i></button>
          <input id="pi-agent-load-session-file" type="file" accept=".json,application/json" hidden />
          <button id="pi-agent-save-session" class="pi-agent-btn pi-agent-icon-btn" type="button" title="Save session JSON" aria-label="Save session JSON"><i class="pi pi-save" aria-hidden="true"></i></button>
          <button id="pi-agent-rename-session" class="pi-agent-btn pi-agent-icon-btn" type="button" title="Rename session" aria-label="Rename session"><i class="pi pi-pencil" aria-hidden="true"></i></button>
          <button id="pi-agent-delete-chat" class="pi-agent-btn pi-agent-icon-btn" type="button" title="Delete session" aria-label="Delete session"><i class="pi pi-trash" aria-hidden="true"></i></button>
        </div>
      </div>
      <div class="pi-agent-view-tabs" role="tablist" aria-label="Pi Agent view">
        <div id="pi-agent-terminal-tab" class="pi-agent-view-tab active" role="tab" tabindex="0" aria-selected="true" aria-controls="pi-agent-terminal-pane">Terminal</div>
        <div id="pi-agent-chat-tab" class="pi-agent-view-tab" role="tab" tabindex="0" aria-selected="false" aria-controls="pi-agent-chat-pane">Chat</div>
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
        <strong>Structured Chat display</strong>
        <label class="pi-agent-check"><input id="pi-agent-show-reasoning" type="checkbox" checked /> Show reasoning</label>
        <label class="pi-agent-check"><input id="pi-agent-show-tools" type="checkbox" checked /> Show tool calls and tool activity</label>
        <div class="pi-agent-help">Both are visible by default. Terminal view is the real Pi TUI and follows Pi's own display/settings directly.</div>
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
        <label class="pi-agent-check"><input id="pi-agent-preemptive-handoff" type="checkbox" checked /> Durable context checkpoint + in-place Pi compaction</label>
        <div class="pi-agent-help">ComfyUI-Pi keeps Pi's native compaction enabled. At the configured threshold it saves a bounded durable checkpoint and asks Pi to compact the current session in place. No new Pi session is started.</div>
        <div class="pi-agent-field"><label for="pi-agent-handoff-threshold">Handoff threshold (%)</label><input id="pi-agent-handoff-threshold" class="pi-agent-input" type="number" min="80" max="95" step="0.5" value="82.5" /></div>
        <div class="pi-agent-field"><label for="pi-agent-handoff-max-chars">Maximum handoff size (characters)</label><input id="pi-agent-handoff-max-chars" class="pi-agent-input" type="number" min="4000" max="16000" step="500" value="8000" /></div>
        <div class="pi-agent-field"><label for="pi-agent-timeout">Timeout in seconds</label><input id="pi-agent-timeout" class="pi-agent-input" type="number" min="10" max="3600" value="180" /></div>
      </div>
      <div id="pi-agent-terminal-pane" class="pi-agent-terminal-pane" role="tabpanel" aria-labelledby="pi-agent-terminal-tab">
        <div id="pi-agent-terminal-host" class="pi-agent-terminal-host" role="application" aria-label="Real Pi interactive terminal"></div>
        <div id="pi-agent-terminal-status" class="pi-agent-terminal-status">Terminal starts when this view opens.</div>
      </div>
      <div id="pi-agent-chat-pane" class="pi-agent-chat-pane" role="tabpanel" aria-labelledby="pi-agent-chat-tab" hidden>
        <div id="pi-agent-messages" class="pi-agent-messages" aria-live="polite"></div>
        <div class="pi-agent-composer">
          <textarea id="pi-agent-chat-input" class="pi-agent-textarea" placeholder="Message Pi Agent… Type / for Pi commands. Paste text normally. Enter sends; Shift+Enter adds a new line."></textarea>
          <div id="pi-agent-command-menu" class="pi-agent-command-menu" role="listbox" aria-label="Pi slash commands"></div>
        </div>
        <div id="pi-agent-chat-actions" class="pi-agent-composer-actions" hidden>
          <button id="pi-agent-stop" class="pi-agent-btn pi-agent-hidden" type="button">Stop</button>
        </div>
      </div>
      <div class="pi-agent-shared-controls">
        <div id="pi-agent-statusline" class="pi-agent-statusline"></div>
        <div class="pi-agent-model-switcher" aria-label="Pi provider and model selection">
          <div class="pi-agent-field"><label for="pi-agent-provider">Provider</label><select id="pi-agent-provider" class="pi-agent-input"><option value="pi-default">Pi default / current configured model</option></select></div>
          <div class="pi-agent-field"><label for="pi-agent-model">Model</label><select id="pi-agent-model" class="pi-agent-input"><option value="">Pi default model</option></select></div>
        </div>
      </div>
    </div>`;

  const ui = {
    sessionSelect: el.querySelector("#pi-agent-session-select"),
    newChat: el.querySelector("#pi-agent-new-chat"),
    loadSessionButton: el.querySelector("#pi-agent-load-session"),
    loadSessionFile: el.querySelector("#pi-agent-load-session-file"),
    saveSessionButton: el.querySelector("#pi-agent-save-session"),
    renameSessionButton: el.querySelector("#pi-agent-rename-session"),
    deleteChat: el.querySelector("#pi-agent-delete-chat"),
    settingsToggle: el.querySelector("#pi-agent-settings-toggle"),
    settings: el.querySelector("#pi-agent-chat-settings"),
    terminalTab: el.querySelector("#pi-agent-terminal-tab"),
    chatTab: el.querySelector("#pi-agent-chat-tab"),
    terminalPane: el.querySelector("#pi-agent-terminal-pane"),
    terminalHost: el.querySelector("#pi-agent-terminal-host"),
    terminalStatus: el.querySelector("#pi-agent-terminal-status"),
    chatPane: el.querySelector("#pi-agent-chat-pane"),
    chatActions: el.querySelector("#pi-agent-chat-actions"),
    project: el.querySelector("#pi-agent-project"),
    projectContext: el.querySelector("#pi-agent-project-context"),
    includeWorkflow: el.querySelector("#pi-agent-include-workflow"),
    showReasoning: el.querySelector("#pi-agent-show-reasoning"),
    showTools: el.querySelector("#pi-agent-show-tools"),
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
    stop: el.querySelector("#pi-agent-stop"),
    runtimePill: el.querySelector("#pi-agent-runtime-pill"),
    contextPill: el.querySelector("#pi-agent-context-pill"),
  };

  ui.showReasoning.checked = CHAT_STATE.showReasoning;
  ui.showTools.checked = CHAT_STATE.showTools;
  ui.terminalHost.addEventListener("keydown", (event) => event.stopPropagation());
  ui.terminalHost.addEventListener("keyup", (event) => event.stopPropagation());
  ui.settingsToggle.addEventListener("click", () => { ui.settings.hidden = !ui.settings.hidden; });
  const activateTab = (view) => (event) => {
    if (event.type === "keydown" && !["Enter", " ", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
    if (event.type === "keydown") event.preventDefault();
    if (view === "terminal" && ui.terminalTab.getAttribute("aria-disabled") === "true") return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      const nextView = view === "terminal" ? "chat" : "terminal";
      const target = nextView === "terminal" ? ui.terminalTab : ui.chatTab;
      if (target.getAttribute("aria-disabled") === "true") return;
      target.focus();
      switchView(ui, nextView);
      return;
    }
    switchView(ui, view);
  };
  ui.terminalTab.addEventListener("click", activateTab("terminal"));
  ui.terminalTab.addEventListener("keydown", activateTab("terminal"));
  ui.chatTab.addEventListener("click", activateTab("chat"));
  ui.chatTab.addEventListener("keydown", activateTab("chat"));
  ui.showReasoning.addEventListener("change", async () => {
    CHAT_STATE.showReasoning = ui.showReasoning.checked;
    localStorage.setItem("ComfyUIPi.ShowReasoning", String(CHAT_STATE.showReasoning));
    if (CHAT_STATE.sessionId) await loadSession(ui, CHAT_STATE.sessionId);
  });
  ui.showTools.addEventListener("change", async () => {
    CHAT_STATE.showTools = ui.showTools.checked;
    localStorage.setItem("ComfyUIPi.ShowTools", String(CHAT_STATE.showTools));
    if (CHAT_STATE.sessionId) await loadSession(ui, CHAT_STATE.sessionId);
  });
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
    const previous = CHAT_STATE.sessionId;
    if (previous && CHAT_STATE.view === "terminal") {
      try { await fetchJson("/pi-agent/terminal/stop", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: previous }) }); } catch {}
    }
    const session = await createSession(ui);
    await refreshSessions(ui, session.session_id);
    if (CHAT_STATE.terminal) CHAT_STATE.terminal.reset();
    if (CHAT_STATE.view === "terminal") await startTerminal(ui); else ui.textarea.focus();
  });
  ui.loadSessionButton.addEventListener("click", () => {
    if (!CHAT_STATE.busy) ui.loadSessionFile.click();
  });
  ui.loadSessionFile.addEventListener("change", async () => {
    const [file] = ui.loadSessionFile.files || [];
    try {
      if (file) await loadSessionFile(ui, file);
    } catch (error) {
      ui.statusline.textContent = String(error);
    } finally {
      ui.loadSessionFile.value = "";
    }
  });
  ui.saveSessionButton.addEventListener("click", async () => {
    try { await saveSessionFile(ui); } catch (error) { ui.statusline.textContent = String(error); }
  });
  ui.renameSessionButton.addEventListener("click", async () => {
    try { await renameCurrentSession(ui); } catch (error) { ui.statusline.textContent = String(error); }
  });
  ui.deleteChat.addEventListener("click", async () => {
    if (!CHAT_STATE.sessionId || CHAT_STATE.busy) return;
    const deletingSessionId = CHAT_STATE.sessionId;
    await stopTerminalForSessionChange(deletingSessionId);
    await fetchJson(`/pi-agent/chat/session/${encodeURIComponent(deletingSessionId)}`, { method: "DELETE" });
    rememberSessionId("");
    await refreshSessions(ui);
    if (CHAT_STATE.view === "terminal") await startTerminal(ui);
    else ui.textarea.focus();
  });
  ui.sessionSelect.addEventListener("change", async () => {
    const previous = CHAT_STATE.sessionId;
    if (previous && previous !== ui.sessionSelect.value && CHAT_STATE.view === "terminal") {
      try { await fetchJson("/pi-agent/terminal/stop", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: previous }) }); } catch {}
    }
    await loadSession(ui, ui.sessionSelect.value);
    await refreshCommandCatalog(ui);
    if (CHAT_STATE.terminal) CHAT_STATE.terminal.reset();
    if (CHAT_STATE.view === "terminal") await startTerminal(ui);
  });

  return ui;
}

async function initializeSidebar(el, placement = "sidebar") {
  const ui = buildSidebar(el, placement);

  // Restore the detached terminal before doing any provider/status/session HTTP work.
  // This makes expanding the panel visually instantaneous: the exact xterm screen and
  // scrollback from before collapse are visible while the lightweight UI metadata refreshes.
  if (CHAT_STATE.terminal && CHAT_STATE.view === "terminal") {
    ensureTerminalInstance(ui);
    ui.terminalStatus.textContent = CHAT_STATE.terminalSocket?.readyState === WebSocket.OPEN
      ? "Connected to Pi terminal." : "Restoring Pi terminal connection…";
  }

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
    const terminalCapability = await fetchJson("/pi-agent/terminal/capability");
    CHAT_STATE.terminalSupported = Boolean(terminalCapability.supported);
    ui.terminalTab.setAttribute("aria-disabled", String(!CHAT_STATE.terminalSupported));
    ui.terminalTab.tabIndex = CHAT_STATE.terminalSupported ? 0 : -1;
    ui.terminalTab.title = terminalCapability.message || "Real Pi terminal";
    if (!CHAT_STATE.terminalSupported) {
      ui.terminalStatus.textContent = terminalCapability.message || "Native terminal unavailable; using structured Chat.";
      CHAT_STATE.view = "chat";
    }
  } catch (error) {
    CHAT_STATE.terminalSupported = false;
    ui.terminalTab.setAttribute("aria-disabled", "true");
    ui.terminalTab.tabIndex = -1;
    ui.terminalStatus.textContent = `Terminal unavailable: ${String(error)}`;
    CHAT_STATE.view = "chat";
  }
  try {
    await refreshSessions(ui);
  } catch (error) {
    ui.messages.innerHTML = `<div class="pi-agent-empty"><strong>Unable to load chats.</strong><br>${escapeHtml(error)}</div>`;
  }
  switchView(ui, CHAT_STATE.terminalSupported ? CHAT_STATE.view : "chat");
  if (CHAT_STATE.terminalStatusTimer) {
    clearInterval(CHAT_STATE.terminalStatusTimer);
    CHAT_STATE.terminalStatusTimer = null;
  }
  if (CHAT_STATE.terminalSupported) {
    CHAT_STATE.terminalStatusTimer = setInterval(async () => {
      if (CHAT_STATE.view !== "terminal" || !CHAT_STATE.sessionId) return;
      try {
        const status = await fetchJson(`/pi-agent/terminal/status/${encodeURIComponent(CHAT_STATE.sessionId)}`);
        const percent = Number(status.bridge?.context_percent);
        if (status.title) {
          const option = [...ui.sessionSelect.options].find((item) => item.value === CHAT_STATE.sessionId);
          if (option) option.textContent = String(status.title);
          const sessionMeta = CHAT_STATE.sessions.find((item) => item.session_id === CHAT_STATE.sessionId);
          if (sessionMeta) sessionMeta.title = String(status.title);
        }
        if (status.recovering) {
          ui.terminalStatus.textContent = status.message || "Pi is automatically resuming the saved session…";
        } else if (!status.running) {
          ui.terminalStatus.textContent = status.message || "Pi interactive terminal is stopped.";
        } else if (CHAT_STATE.terminalSocket?.readyState === WebSocket.OPEN) {
          ui.terminalStatus.textContent = Number(status.resume_count || 0) > 0
            ? `Connected to Pi terminal. Automatic recoveries: ${status.resume_count}.`
            : "Connected to Pi terminal.";
        }
        if (status.running && Number(status.output_bytes || 0) === 0 && Date.now() / 1000 - Number(status.started_at || 0) > 3) {
          ui.terminalStatus.textContent = status.message || "Pi is running but has not produced terminal output yet.";
        }
        if (Number.isFinite(percent)) {
          const ratio = percent > 1 ? percent / 100 : percent;
          const guard = {
            threshold: Number(ui.handoffThreshold.value || 82.5) / 100,
            handoff_count: Number(status.bridge?.handoff_count || 0),
            last_pressure: { ratio },
          };
          updateContextPill(ui, guard);
        }
      } catch {}
    }, 2000);
  }
}

app.registerExtension({
  name: "badgids.ComfyUI.PiAgent",
  settings: [
    {
      id: "PiAgent.UI.ShowSidebar",
      name: "Pi Agent: Enable interface after restart",
      type: "boolean",
      defaultValue: false,
      tooltip: "Enables the Pi Agent Terminal/Chat interface. Choose its location with the Pi Agent interface placement setting. All Pi Agent features remain available as nodes when disabled."
    },
    {
      id: "PiAgent.UI.Placement",
      name: "Pi Agent: Interface placement",
      type: "combo",
      options: ["Left sidebar", "Bottom panel"],
      defaultValue: "Left sidebar",
      tooltip: "Choose whether Pi Agent appears in the left sidebar or in ComfyUI's bottom panel. Refresh the ComfyUI browser page after changing this setting."
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
    // ComfyUI calls extension setup() at the end of frontend startup. Only now
    // is app.canvas/rootGraph safe for loadGraphData(). The capture bridge must
    // not be exposed earlier merely because this ES module has been evaluated.
    const isPlaywrightCapturePage =
      new URLSearchParams(window.location.search).get("comfyui_pi_playwright_capture") === "1";
    if (isPlaywrightCapturePage) {
      if (!installPlaywrightCaptureBridge()) {
        throw new Error("ComfyUI-Pi Playwright capture page reached extension setup without a ready graph canvas.");
      }
    } else {
      startWorkflowScreenshotWorker();
    }
    const enabled = app.extensionManager?.setting?.get?.("PiAgent.UI.ShowSidebar") ?? false;
    if (!enabled) return;
    const placement = app.extensionManager?.setting?.get?.("PiAgent.UI.Placement") ?? "Left sidebar";
    if (placement === "Bottom panel") {
      // ComfyUI's public bottomPanelTabs API registers extension-owned tabs in the
      // same lower workspace used by its terminal/log panels. Registering this small
      // runtime extension here lets the persisted placement setting choose exactly one
      // Pi Agent location on page load instead of rendering duplicate interfaces.
      app.registerExtension({
        name: "badgids.ComfyUI.PiAgent.BottomPanel",
        bottomPanelTabs: [
          {
            id: "pi-agent-bottom-panel",
            title: "Pi Agent",
            type: "custom",
            targetPanel: "terminal",
            render: async (el) => {
              await initializeSidebar(el, "bottom");
            },
            destroy: () => detachPiInterface()
          }
        ]
      });
      return;
    }
    if (!app.extensionManager?.registerSidebarTab) return;
    app.extensionManager.registerSidebarTab({
      id: "pi-agent-sidebar",
      icon: "pi pi-comments",
      title: "Pi Agent",
      tooltip: "Chat with and instruct Pi Agent directly inside ComfyUI",
      type: "custom",
      render: async (el) => {
        await initializeSidebar(el, "sidebar");
      },
      destroy: () => detachPiInterface()
    });
  }
});
