/**
 * ComfyUI-Pi terminal bridge.
 *
 * This is the single explicitly loaded Pi extension used by Terminal mode. It keeps
 * startup sparse and injects only task-specific ComfyUI/node-pack guidance when a user
 * actually submits a prompt. The visible text in Pi remains the user's original input.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Buffer } from "buffer";
import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "fs";
import { dirname, isAbsolute, relative, resolve } from "path";
import { Type } from "typebox";
import { registerDynamicMcpTools } from "./dynamic-mcp-tools";

const COMFYUI_PI_COMPACTION_INSTRUCTIONS =
  "Preserve continuity for the current ComfyUI task using Pi's normal compaction format. " +
  "Preserve the user's current objective and constraints, completed and in-progress work, " +
  "key decisions, blockers, exact relevant file/workflow/model identifiers, and concrete next steps. " +
  "Keep large workflow/project artifacts referenced by path instead of embedding them. " +
  "Preserve which ComfyUI/node-pack procedures may need to be reloaded on demand, but do not inline " +
  "large manuals or whole workflows. Continue the same task after compaction; do not restart from scratch.";

function readJson(path: string): any {
  if (!path) return {};
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return {}; }
}

function readPendingHandoff(markerPath: string, maxChars: number): { text: string; path: string } | undefined {
  if (!markerPath || !existsSync(markerPath)) return undefined;
  try {
    const marker = readJson(markerPath);
    const handoffPath = String(marker?.handoff_path || "");
    if (!handoffPath || !existsSync(handoffPath)) return undefined;
    const limit = Math.max(4000, Math.min(16000, Number(maxChars || 8000)));
    const text = readFileSync(handoffPath, "utf8").slice(0, limit).trim();
    if (!text) return undefined;
    return { text, path: handoffPath };
  } catch {
    return undefined;
  }
}

function normalizedRatio(percent: unknown, tokens: unknown, contextWindow: unknown): number {
  const p = Number(percent);
  if (Number.isFinite(p) && p > 0) return p > 1 ? p / 100 : p;
  const t = Number(tokens);
  const w = Number(contextWindow);
  return Number.isFinite(t) && Number.isFinite(w) && t > 0 && w > 0 ? t / w : 0;
}

function configuredThreshold(config: any): number {
  let threshold = Number(config?.handoff_threshold || 0.825);
  if (threshold > 1) threshold /= 100;
  return Math.max(0.80, Math.min(0.95, threshold));
}

function branchContainsEntry(entries: readonly unknown[], entryId: string): boolean {
  if (!entryId) return false;
  return entries.some((entry) =>
    Boolean(entry && typeof entry === "object" && String((entry as { id?: unknown }).id || "") === entryId)
  );
}

function readHandoffText(metadata: any, maxChars: number): string {
  const path = String(metadata?.path || "");
  if (!path || !existsSync(path)) return "";
  const limit = Math.max(4000, Math.min(16000, Number(maxChars || 8000)));
  try { return readFileSync(path, "utf8").slice(0, limit).trim(); } catch { return ""; }
}

function writeBridgeState(ctx: any, extra: Record<string, unknown> = {}) {
  const statePath = process.env.COMFYUI_PI_BRIDGE_STATE || "";
  if (!statePath) return;
  const usage = ctx.getContextUsage?.();
  const payload = {
    updated_at: Date.now() / 1000,
    context_tokens: usage?.tokens ?? null,
    context_window: usage?.contextWindow ?? ctx.model?.contextWindow ?? 0,
    context_percent: usage?.percent ?? null,
    session_file: ctx.sessionManager.getSessionFile?.() || "",
    session_id: ctx.sessionManager.getSessionId?.() || "",
    ...extra,
  };
  try { writeFileSync(statePath, JSON.stringify(payload, null, 2)); } catch {}
}

export default function comfyUiPiTerminalBridge(pi: ExtensionAPI) {
  registerDynamicMcpTools(pi);

  let latestInput = "";
  let latestSource = "interactive";
  let activeTaskInput = "";
  let compactionPrepared = false;
  let compactionRequested = false;
  let pendingHandoff: any = undefined;
  let pendingHandoffText = "";
  let compactionAnchorId = "";
  let compactionSessionFile = "";
  let compactionSessionId = "";
  let continuationSerial = 0;


  const workflowToolConfig = () => readJson(process.env.COMFYUI_PI_BRIDGE_CONFIG || "");

  const workflowPathAllowed = (path: string): boolean => {
    const candidate = resolve(String(path || ""));
    const config = workflowToolConfig();
    const roots = [String(config.project_directory || ""), process.cwd()]
      .filter(Boolean)
      .map((item) => resolve(item));
    return roots.some((root) => {
      const rel = relative(root, candidate);
      return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
    });
  };

  const requestJson = async (url: string, init?: any): Promise<any> => {
    const response = await fetch(url, init);
    const text = await response.text();
    let payload: any = {};
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = { error: text }; }
    if (!response.ok && !payload?.error) payload.error = `HTTP ${response.status}`;
    return payload;
  };

  const currentComfyBase = () => String(workflowToolConfig().comfyui_base_url || "").replace(/\/+$/, "");

  pi.registerTool({
    name: "comfyui_search_paths",
    label: "ComfyUI Live Search Paths",
    description:
      "Return the CURRENT running ComfyUI instance's registered filesystem search roots. " +
      "These are authoritative for installed assets and already include ComfyUI defaults, startup directory overrides, " +
      "extra_model_paths.yaml, and every --extra-model-paths-config file loaded by ComfyUI. " +
      "Use this before assuming default models, workflows, or custom_nodes directories.",
    parameters: Type.Object({}),
    async execute() {
      const base = currentComfyBase();
      if (!base) {
        return {
          content: [{ type: "text", text: "ERROR: no current ComfyUI base URL; live search paths are unavailable." }],
          details: { ok: false, error: "missing_comfyui_base_url" },
        };
      }
      const result = await requestJson(`${base}/pi-agent/discovery/paths`);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2).slice(0, 30000) }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "comfyui_find_installed",
    label: "Find Installed ComfyUI Assets",
    description:
      "Search the CURRENT ComfyUI installation for real installed models, workflow JSON files, custom-node packs, " +
      "or files in explicitly requested folder_paths categories. Searches every live registered root, including paths " +
      "loaded from extra_model_paths.yaml and --extra-model-paths-config. Use this instead of guessing default locations.",
    parameters: Type.Object({
      query: Type.Optional(Type.String()),
      kinds: Type.Optional(Type.Array(Type.String())),
      categories: Type.Optional(Type.Array(Type.String())),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 500 })),
    }),
    async execute(_toolCallId, params) {
      const base = currentComfyBase();
      if (!base) {
        return {
          content: [{ type: "text", text: "ERROR: no current ComfyUI base URL; installed-asset discovery cannot run." }],
          details: { ok: false, error: "missing_comfyui_base_url" },
        };
      }
      const result = await requestJson(`${base}/pi-agent/discovery/find`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: String(params.query || ""),
          kinds: Array.isArray(params.kinds) ? params.kinds : undefined,
          categories: Array.isArray(params.categories) ? params.categories : undefined,
          limit: Number(params.limit || 200),
        }),
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2).slice(0, 30000) }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "comfyui_live_nodes",
    label: "ComfyUI Live Nodes",
    description:
      "Query the CURRENT connected ComfyUI instance for real installed node classes and live /object_info schemas. " +
      "Use this before creating or connecting workflow nodes. Never invent a node or socket that is absent here.",
    parameters: Type.Object({
      node_types: Type.Optional(Type.Array(Type.String())),
    }),
    async execute(_toolCallId, params) {
      const config = workflowToolConfig();
      const base = String(config.comfyui_base_url || "").replace(/\/+$/, "");
      if (!base) {
        return {
          content: [{ type: "text", text: "ERROR: no current ComfyUI base URL. Do not generate a workflow from guessed nodes." }],
          details: { ok: false, error: "missing_comfyui_base_url" },
        };
      }
      const requested = Array.isArray(params.node_types) ? params.node_types.filter(Boolean) : [];
      let result: any;
      if (!requested.length) {
        result = await requestJson(`${base}/pi-agent/workflow/capabilities`);
      } else {
        result = {};
        for (const nodeType of requested) {
          const info = await requestJson(`${base}/object_info/${encodeURIComponent(nodeType)}`);
          result[nodeType] = info?.[nodeType] ?? null;
        }
      }
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2).slice(0, 30000) }],
        details: { ok: true, result },
      };
    },
  });

  pi.registerTool({
    name: "comfyui_workflow_finalize",
    label: "Finalize ComfyUI Workflow",
    description:
      "MANDATORY final gate for generated workflows. Validates current live nodes/sockets, forces Nodes 2.0 Vue-corrected layout, " +
      "enforces >=6px node clearance, requires a real output node, and runs native prompt validation when api_prompt_path is supplied. " +
      "Do not call a workflow complete until completion_verified=true.",
    parameters: Type.Object({
      workflow_path: Type.String(),
      api_prompt_path: Type.Optional(Type.String()),
      organize: Type.Optional(Type.Boolean()),
    }),
    async execute(_toolCallId, params) {
      const workflowPath = String(params.workflow_path || "");
      const apiPath = String(params.api_prompt_path || "");
      if (!workflowPathAllowed(workflowPath) || (apiPath && !workflowPathAllowed(apiPath))) {
        return {
          content: [{ type: "text", text: "ERROR: workflow path is outside the current project/cwd safety boundary." }],
          details: { ok: false, error: "path_outside_allowed_roots" },
        };
      }
      if (!existsSync(workflowPath)) {
        return {
          content: [{ type: "text", text: `ERROR: workflow file does not exist: ${workflowPath}` }],
          details: { ok: false, error: "workflow_missing" },
        };
      }
      const config = workflowToolConfig();
      const base = String(config.comfyui_base_url || "").replace(/\/+$/, "");
      if (!base) {
        return {
          content: [{ type: "text", text: "ERROR: no current ComfyUI base URL; live workflow validation cannot run." }],
          details: { ok: false, error: "missing_comfyui_base_url" },
        };
      }

      let workflow: any;
      let apiPrompt: any = undefined;
      try {
        workflow = JSON.parse(readFileSync(workflowPath, "utf8"));
        if (apiPath) apiPrompt = JSON.parse(readFileSync(apiPath, "utf8"));
      } catch (error) {
        return {
          content: [{ type: "text", text: `ERROR: could not read workflow JSON: ${String(error)}` }],
          details: { ok: false, error: String(error) },
        };
      }

      const result = await requestJson(`${base}/pi-agent/workflow/finalize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow,
          api_prompt: apiPrompt,
          organize: params.organize !== false,
          minimum_node_gap_px: 6,
        }),
      });
      if (result?.valid && result?.workflow) {
        writeFileSync(workflowPath, JSON.stringify(result.workflow, null, 2));
      }
      const state = result?.completion_verified
        ? "COMPLETE: live schema + layout + output + native ComfyUI prompt validation passed."
        : "NOT COMPLETE: fix every gate error and/or provide a native-valid API prompt before claiming completion.";
      return {
        content: [{ type: "text", text: `${state}\n${JSON.stringify({
          valid: result?.valid,
          runnable_candidate: result?.runnable_candidate,
          completion_verified: result?.completion_verified,
          renderer: result?.workflow_renderer,
          minimum_node_gap_px: result?.minimum_node_gap_px,
          issues: result?.issues,
          native_validation: result?.native_validation,
        }, null, 2)}` }],
        details: result,
      };
    },
  });

  const runMarkdownDiagramCli = async (mode: "flowchart" | "node", payload: Record<string, unknown>) => {
    const configPath = process.env.COMFYUI_PI_BRIDGE_CONFIG || "";
    if (!configPath) throw new Error("ComfyUI-Pi bridge config is unavailable.");
    const python = process.env.COMFYUI_PI_PYTHON || "python3";
    const requestPath = `${configPath}.diagram-${Date.now()}-${Math.random().toString(16).slice(2)}.json`;
    try {
      writeFileSync(requestPath, JSON.stringify(payload));
      const result = await pi.exec(python, [
        "-m", "comfy_pi_agent.markdown_diagram_cli",
        mode,
        "--request", requestPath,
      ]);
      const raw = String(result.stdout || "").trim();
      if (!raw) throw new Error("Markdown diagram helper returned no result.");
      return JSON.parse(raw);
    } finally {
      try { unlinkSync(requestPath); } catch {}
    }
  };

  pi.registerTool({
    name: "comfyui_markdown_flowchart",
    label: "Markdown ASCII Flowchart + Image",
    description:
      "Create/update a Markdown flowchart from one semantic graph. For GENERATED diagrams, always provide semantic nodes and edges; " +
      "ComfyUI-Pi independently renders canonical ASCII and a polished vector SVG from that graph, so the image is never a tracing or screenshot of the ASCII. " +
      "Use ascii_text only for EXISTING hand-authored ASCII, which is parsed through Ascidia when available.",
    parameters: Type.Object({
      markdown_path: Type.String(),
      diagram_id: Type.String(),
      alt_text: Type.Optional(Type.String()),
      direction: Type.Optional(Type.String()),
      nodes: Type.Optional(Type.Array(Type.Object({
        id: Type.String(),
        label: Type.String(),
        shape: Type.Optional(Type.String()),
      }))),
      edges: Type.Optional(Type.Array(Type.Object({
        from: Type.String(),
        to: Type.String(),
        label: Type.Optional(Type.String()),
      }))),
      ascii_text: Type.Optional(Type.String()),
      include_ascii: Type.Optional(Type.Boolean()),
    }),
    async execute(_toolCallId, params) {
      const markdownPath = String(params.markdown_path || "");
      if (!markdownPath || !workflowPathAllowed(markdownPath)) {
        return {
          content: [{ type: "text", text: "ERROR: Markdown path is outside the current project/cwd safety boundary." }],
          details: { ok: false, error: "path_outside_allowed_roots" },
        };
      }
      const asciiText = String(params.ascii_text || "");
      const nodes = Array.isArray(params.nodes) ? params.nodes : [];
      if (!asciiText.trim() && !nodes.length) {
        return {
          content: [{ type: "text", text: "ERROR: provide either ascii_text or at least one flowchart node." }],
          details: { ok: false, error: "empty_diagram" },
        };
      }
      const direction = String(params.direction || "TB").toUpperCase() === "LR" ? "LR" : "TB";
      try {
        const result = await runMarkdownDiagramCli("flowchart", {
          markdown_path: markdownPath,
          diagram_id: String(params.diagram_id || "flowchart"),
          alt_text: String(params.alt_text || "Flowchart"),
          include_ascii: params.include_ascii !== false,
          ascii_text: asciiText,
          spec: {
            direction,
            nodes,
            edges: Array.isArray(params.edges) ? params.edges : [],
          },
        });
        return {
          content: [{ type: "text", text:
            `Markdown flowchart written.\nMarkdown: ${result.markdown_path}\nImage: ${result.image_path}\nRenderer: ${result.renderer}` }],
          details: result,
        };
      } catch (error) {
        return {
          content: [{ type: "text", text: `ERROR: ${String(error)}` }],
          details: { ok: false, error: String(error) },
        };
      }
    },
  });

  pi.registerTool({
    name: "comfyui_markdown_node_image",
    label: "Markdown Exact ComfyUI Node Image",
    description:
      "Capture an EXACT image of the actual installed ComfyUI node as rendered by the CURRENT ComfyUI frontend. " +
      "ComfyUI itself creates and renders the node; ComfyUI-Pi only validates the installed type, measures the real Vue node DOM, " +
      "captures that exact bounding box with Playwright, and inserts the PNG into Markdown. " +
      "Never reconstruct, approximate, synthesize, or fall back to SVG/HTML/CSS/Canvas artwork.",
    parameters: Type.Object({
      markdown_path: Type.String(),
      workflow_path: Type.Optional(Type.String()),
      node_id: Type.Optional(Type.String()),
      node_type: Type.Optional(Type.String()),
      image_id: Type.Optional(Type.String()),
      alt_text: Type.Optional(Type.String()),
    }),
    async execute(_toolCallId, params) {
      const markdownPath = resolve(String(params.markdown_path || ""));
      const workflowPath = String(params.workflow_path || "")
        ? resolve(String(params.workflow_path))
        : "";
      if (!String(params.markdown_path || "") || !workflowPathAllowed(markdownPath) ||
          (workflowPath && !workflowPathAllowed(workflowPath))) {
        return {
          content: [{ type: "text", text: "ERROR: Markdown/workflow path is outside the current project/cwd safety boundary." }],
          details: { ok: false, error: "path_outside_allowed_roots" },
        };
      }
      if (workflowPath && !existsSync(workflowPath)) {
        return {
          content: [{ type: "text", text: `ERROR: workflow file does not exist: ${workflowPath}` }],
          details: { ok: false, error: "workflow_missing" },
        };
      }

      let nodeId = String(params.node_id || "").trim();
      let nodeType = String(params.node_type || "").trim();
      let workflow: any = undefined;
      if (workflowPath) {
        try {
          workflow = JSON.parse(readFileSync(workflowPath, "utf8"));
        } catch (error) {
          return {
            content: [{ type: "text", text: `ERROR: could not read workflow JSON: ${String(error)}` }],
            details: { ok: false, error: String(error) },
          };
        }
        if (!workflow || !Array.isArray(workflow.nodes)) {
          return {
            content: [{ type: "text", text: "ERROR: workflow_path must contain a serialized ComfyUI UI workflow." }],
            details: { ok: false, error: "invalid_workflow" },
          };
        }
        if (!nodeId && !nodeType) {
          return {
            content: [{ type: "text", text: "ERROR: workflow_path requires node_id or node_type to select the node to capture." }],
            details: { ok: false, error: "missing_node_target" },
          };
        }
        const target = workflow.nodes.find((item: any) =>
          item && typeof item === "object" &&
          (nodeId ? String(item.id) === nodeId : (nodeType && String(item.type) === nodeType))
        );
        if (!target) {
          const wanted = nodeId ? `node id '${nodeId}'` : `node type '${nodeType}'`;
          return {
            content: [{ type: "text", text: `ERROR: ${wanted} was not found in the supplied workflow.` }],
            details: { ok: false, error: "workflow_node_missing" },
          };
        }
        nodeId = String(target.id ?? nodeId);
        nodeType = String(target.type || nodeType).trim();
      }

      if (!nodeId && !nodeType) {
        return {
          content: [{ type: "text", text: "ERROR: provide node_id, node_type, or a workflow containing the requested node." }],
          details: { ok: false, error: "missing_node_target" },
        };
      }

      const config = workflowToolConfig();
      const base = String(config.comfyui_base_url || "").replace(/\/+$/, "");
      if (!base) {
        return {
          content: [{ type: "text", text: "ERROR: current ComfyUI base URL is unavailable; exact node capture cannot run." }],
          details: { ok: false, error: "missing_comfyui_base_url" },
        };
      }

      let liveSchemaVerified = false;
      if (nodeType) {
        const live = await requestJson(`${base}/object_info/${encodeURIComponent(nodeType)}`);
        if (!live?.[nodeType]) {
          return {
            content: [{ type: "text", text: `ERROR: node type '${nodeType}' is not installed in the current ComfyUI instance.` }],
            details: { ok: false, error: "node_not_installed", node_type: nodeType },
          };
        }
        liveSchemaVerified = true;
      }

      const markdownStem = markdownPath.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "") || "document";
      const rawImageId = String(params.image_id || `node-${nodeId || nodeType}`);
      const imageId = rawImageId
        .replace(/[^a-zA-Z0-9._-]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 96) || "node";
      const outputPath = resolve(dirname(markdownPath), `${markdownStem}_assets`, `${imageId}.png`);
      if (!workflowPathAllowed(outputPath)) {
        return {
          content: [{ type: "text", text: "ERROR: generated node-image path is outside the current project/cwd safety boundary." }],
          details: { ok: false, error: "path_outside_allowed_roots" },
        };
      }

      let response: any;
      try {
        response = await fetch(`${base}/pi-agent/screenshot/request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: "node_exact",
            node_id: nodeId,
            node_type: nodeType,
            workflow,
            padding_px: 0,
            pixel_ratio: 1.5,
            timeout_seconds: 35,
          }),
        });
      } catch (error) {
        return {
          content: [{ type: "text", text: `ERROR: could not contact ComfyUI exact-node capture broker: ${String(error)}` }],
          details: { ok: false, error: String(error) },
        };
      }
      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        try {
          const body = await response.json() as any;
          message = String(body?.error || message);
        } catch {
          try { message = await response.text(); } catch {}
        }
        return {
          content: [{ type: "text", text: `ERROR: exact installed-node capture failed: ${message}` }],
          details: { ok: false, error: message },
        };
      }

      const png = Buffer.from(await response.arrayBuffer());
      if (!png.length) {
        return {
          content: [{ type: "text", text: "ERROR: ComfyUI returned an empty exact-node PNG." }],
          details: { ok: false, error: "empty_png" },
        };
      }

      const width = Number(response.headers.get("x-comfyui-pi-width") || 0);
      const height = Number(response.headers.get("x-comfyui-pi-height") || 0);
      const actualPadding = Number(response.headers.get("x-comfyui-pi-padding") || 0);
      const nodeWidth = Number(response.headers.get("x-comfyui-pi-node-width") || 0);
      const nodeHeight = Number(response.headers.get("x-comfyui-pi-node-height") || 0);
      const actualNodeId = String(response.headers.get("x-comfyui-pi-node-id") || nodeId);
      const actualNodeType = String(response.headers.get("x-comfyui-pi-node-type") || nodeType);
      const captureBackend = String(response.headers.get("x-comfyui-pi-capture-backend") || "");
      if (actualPadding !== 0 || width <= 0 || height <= 0 ||
          nodeWidth <= 0 || nodeHeight <= 0 || width !== nodeWidth || height !== nodeHeight ||
          captureBackend !== "playwright-page-screenshot") {
        return {
          content: [{ type: "text", text:
            "ERROR: exact-node capture contract was not satisfied; refusing to save an approximate image." }],
          details: {
            ok: false,
            error: "exact_node_crop_mismatch",
            padding_px: actualPadding,
            width,
            height,
            node_width_px: nodeWidth,
            node_height_px: nodeHeight,
            capture_backend: captureBackend,
          },
        };
      }

      mkdirSync(dirname(outputPath), { recursive: true });
      writeFileSync(outputPath, png);
      upsertScreenshotMarkdown(
        markdownPath,
        outputPath,
        imageId,
        String(params.alt_text || actualNodeType || `ComfyUI node ${actualNodeId}`),
      );

      const details = {
        ok: true,
        exact_node_capture: true,
        markdown_path: markdownPath,
        image_path: outputPath,
        node_id: actualNodeId,
        node_type: actualNodeType,
        padding_px: actualPadding,
        width,
        height,
        node_width_px: nodeWidth,
        node_height_px: nodeHeight,
        renderer: "real-comfyui-playwright-png",
        capture_backend: captureBackend,
        live_schema_verified: liveSchemaVerified,
      };
      return {
        content: [{ type: "text", text:
          `Captured exact installed ComfyUI node.\nMarkdown: ${markdownPath}\nImage: ${outputPath}\n` +
          `Node: ${actualNodeType || actualNodeId}\nImage size: ${width}x${height}px` }],
        details,
      };
    },
  });

  const upsertScreenshotMarkdown = (
    markdownPath: string,
    imagePath: string,
    markerId: string,
    altText: string,
  ) => {
    mkdirSync(dirname(markdownPath), { recursive: true });
    const original = existsSync(markdownPath) ? readFileSync(markdownPath, "utf8") : "";
    if (original && !existsSync(`${markdownPath}.comfyui-pi.bak`)) {
      writeFileSync(`${markdownPath}.comfyui-pi.bak`, original);
    }
    const safeMarker = String(markerId || "workflow")
      .replace(/[^a-zA-Z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "workflow";
    const relativeImage = relative(dirname(markdownPath), imagePath).replace(/\\/g, "/");
    const safeAlt = String(altText || "ComfyUI workflow screenshot")
      .replace(/\]/g, "\\]");
    const start = `<!-- COMFYUI-PI-SCREENSHOT:${safeMarker}:START -->`;
    const end = `<!-- COMFYUI-PI-SCREENSHOT:${safeMarker}:END -->`;
    const block = `${start}\n![${safeAlt}](${relativeImage})\n${end}`;
    const escaped = safeMarker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const owned = new RegExp(
      `<!-- COMFYUI-PI-SCREENSHOT:${escaped}:START -->[\\s\\S]*?` +
      `<!-- COMFYUI-PI-SCREENSHOT:${escaped}:END -->`,
      "m",
    );
    const updated = owned.test(original)
      ? original.replace(owned, block)
      : `${original.replace(/\s+$/, "")}${original.trim() ? "\n\n" : ""}${block}\n`;
    writeFileSync(markdownPath, updated);
  };

  pi.registerTool({
    name: "comfyui_workflow_screenshot",
    label: "Capture Live ComfyUI Workflow",
    description:
      "Capture the ACTUAL currently loaded ComfyUI workflow for tutorials/documentation using Playwright page.screenshot(clip=...) against the real rendered frontend. " +
      "mode=workflow captures the real graph/canvas/connections. mode=node clips around the real Vue node DOM bounding box and surrounding workflow context; " +
      "node screenshots ALWAYS enforce at least 300 pixels of padding on every side. The user's visible ComfyUI pan/zoom is not modified. " +
      "Optionally inserts the PNG into Markdown using a project-relative image path. Never substitute a synthetic node renderer or SVG/HTML reconstruction.",
    parameters: Type.Object({
      mode: Type.String({ description: "workflow or node" }),
      output_path: Type.String({ description: "Project/cwd path for the PNG screenshot." }),
      node_id: Type.Optional(Type.String({ description: "Required when mode=node." })),
      padding_px: Type.Optional(Type.Integer({ minimum: 0, maximum: 4000 })),
      pixel_ratio: Type.Optional(Type.Number({ minimum: 1, maximum: 3 })),
      markdown_path: Type.Optional(Type.String({ description: "Optional Markdown file to receive the image link." })),
      alt_text: Type.Optional(Type.String()),
      marker_id: Type.Optional(Type.String()),
    }),
    async execute(_toolCallId, params) {
      const mode = String(params.mode || "workflow").toLowerCase();
      if (!["workflow", "node"].includes(mode)) {
        return {
          content: [{ type: "text", text: "ERROR: mode must be 'workflow' or 'node'." }],
          details: { ok: false, error: "invalid_mode" },
        };
      }
      const nodeId = String(params.node_id || "");
      if (mode === "node" && !nodeId) {
        return {
          content: [{ type: "text", text: "ERROR: node_id is required for mode=node." }],
          details: { ok: false, error: "missing_node_id" },
        };
      }

      const outputPath = resolve(String(params.output_path || ""));
      const markdownPath = String(params.markdown_path || "")
        ? resolve(String(params.markdown_path))
        : "";
      if (!String(params.output_path || "") || !workflowPathAllowed(outputPath) ||
          (markdownPath && !workflowPathAllowed(markdownPath))) {
        return {
          content: [{ type: "text", text: "ERROR: screenshot/Markdown path is outside the current project/cwd safety boundary." }],
          details: { ok: false, error: "path_outside_allowed_roots" },
        };
      }
      if (!outputPath.toLowerCase().endsWith(".png")) {
        return {
          content: [{ type: "text", text: "ERROR: output_path must end in .png." }],
          details: { ok: false, error: "png_required" },
        };
      }

      const config = workflowToolConfig();
      const base = String(config.comfyui_base_url || "").replace(/\/+$/, "");
      if (!base) {
        return {
          content: [{ type: "text", text: "ERROR: no current ComfyUI base URL; live browser screenshots cannot run." }],
          details: { ok: false, error: "missing_comfyui_base_url" },
        };
      }

      const requestedPadding = Number(params.padding_px ?? (mode === "node" ? 300 : 80));
      const padding = mode === "node"
        ? Math.max(300, requestedPadding)
        : Math.max(0, requestedPadding);
      const pixelRatio = Math.max(1, Math.min(3, Number(params.pixel_ratio ?? 1.5)));

      let response: any;
      try {
        response = await fetch(`${base}/pi-agent/screenshot/request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode,
            node_id: nodeId,
            padding_px: padding,
            pixel_ratio: pixelRatio,
            timeout_seconds: 35,
          }),
        });
      } catch (error) {
        return {
          content: [{ type: "text", text: `ERROR: could not contact ComfyUI screenshot broker: ${String(error)}` }],
          details: { ok: false, error: String(error) },
        };
      }

      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        try {
          const body = await response.json() as any;
          message = String(body?.error || message);
        } catch {
          try { message = await response.text(); } catch {}
        }
        return {
          content: [{ type: "text", text: `ERROR: live workflow screenshot failed: ${message}` }],
          details: { ok: false, error: message },
        };
      }

      const png = Buffer.from(await response.arrayBuffer());
      if (!png.length) {
        return {
          content: [{ type: "text", text: "ERROR: ComfyUI returned an empty PNG screenshot." }],
          details: { ok: false, error: "empty_png" },
        };
      }
      mkdirSync(dirname(outputPath), { recursive: true });
      writeFileSync(outputPath, png);

      const width = Number(response.headers.get("x-comfyui-pi-width") || 0);
      const height = Number(response.headers.get("x-comfyui-pi-height") || 0);
      const actualPadding = Number(response.headers.get("x-comfyui-pi-padding") || padding);
      const nodeWidth = Number(response.headers.get("x-comfyui-pi-node-width") || 0);
      const nodeHeight = Number(response.headers.get("x-comfyui-pi-node-height") || 0);

      if (markdownPath) {
        upsertScreenshotMarkdown(
          markdownPath,
          outputPath,
          String(params.marker_id || (mode === "node" ? `node-${nodeId}` : "workflow")),
          String(params.alt_text || (mode === "node"
            ? `ComfyUI node ${nodeId} close-up`
            : "ComfyUI workflow")),
        );
      }

      const details = {
        ok: true,
        mode,
        output_path: outputPath,
        markdown_path: markdownPath,
        node_id: nodeId,
        padding_px: actualPadding,
        width,
        height,
        node_width_px: nodeWidth,
        node_height_px: nodeHeight,
      };
      return {
        content: [{ type: "text", text:
          `Captured live ComfyUI ${mode} screenshot.\n` +
          `PNG: ${outputPath}\n` +
          `${markdownPath ? `Markdown: ${markdownPath}\n` : ""}` +
          `${mode === "node" ? `Node ${nodeId} padding: ${actualPadding}px on every side (minimum 300px).\n` : ""}` +
          `Image size: ${width}x${height}px` }],
        details,
      };
    },
  });

  const createDurableCheckpoint = async (
    ctx: any,
    reason: string,
    tokensOverride?: number,
  ): Promise<{ metadata: any; text: string }> => {
    const configPath = process.env.COMFYUI_PI_BRIDGE_CONFIG || "";
    if (!configPath) throw new Error("ComfyUI-Pi bridge config is unavailable.");
    const config = readJson(configPath);
    const sessionFile = String(ctx.sessionManager.getSessionFile?.() || "");
    if (!sessionFile) throw new Error("Pi did not expose the active session file.");
    const usage = ctx.getContextUsage?.();
    const contextWindow = Number(usage?.contextWindow || ctx.model?.contextWindow || 0);
    const ratio = normalizedRatio(usage?.percent, usage?.tokens, contextWindow);
    const tokensBefore = Number(
      tokensOverride ??
      usage?.tokens ??
      (contextWindow > 0 && ratio > 0 ? Math.round(contextWindow * ratio) : 0)
    );
    const bridgeModule = process.env.COMFYUI_PI_BRIDGE_MODULE || "comfy_pi_agent.terminal_bridge_cli";
    const python = process.env.COMFYUI_PI_PYTHON || "python3";

    const result = await pi.exec(python, [
      "-m", bridgeModule,
      "--create-handoff",
      "--config", configPath,
      "--session-file", sessionFile,
      "--context-tokens", String(tokensBefore),
      "--context-window", String(contextWindow),
      "--reason", reason,
    ]);
    const raw = String(result.stdout || "").trim();
    if (!raw) throw new Error("durable checkpoint command returned no metadata");
    const metadata = JSON.parse(raw);
    const text = readHandoffText(metadata, Number(config.handoff_max_chars || 8000));
    if (!metadata?.path || !text) throw new Error("durable checkpoint file was not written");
    return { metadata, text };
  };

  const maybeRequestEarlyCompaction = async (ctx: any, phase: string): Promise<boolean> => {
    if (compactionRequested) return false;
    const config = readJson(process.env.COMFYUI_PI_BRIDGE_CONFIG || "");
    if (config.preemptive_handoff === false) return false;

    const usage = ctx.getContextUsage?.();
    const ratio = normalizedRatio(usage?.percent, usage?.tokens, usage?.contextWindow);
    const threshold = configuredThreshold(config);
    writeBridgeState(ctx, {
      source: latestSource,
      last_guard: {
        phase,
        ratio,
        threshold,
        action: ratio >= threshold ? "threshold-reached" : "below-threshold",
      },
    });

    // Pi explicitly allows context usage to be unknown after a compaction/turn boundary.
    // If a checkpoint is already prepared, do not strand it just because this later
    // agent_settled sample is null/zero. Only require a threshold sample before prepare.
    if (!compactionPrepared && (!(ratio > 0) || ratio < threshold)) return false;

    // turn_end/agent_end only PREPARE continuity. ExtensionContext.compact() is
    // fire-and-forget, so the fallback compact request still waits until agent_settled,
    // after Pi's own post-run compaction decision has finished.
    if (!compactionPrepared) {
      try {
        const checkpoint = await createDurableCheckpoint(
          ctx,
          "comfyui-threshold",
          usage?.tokens == null ? undefined : Number(usage.tokens),
        );
        pendingHandoff = checkpoint.metadata;
        pendingHandoffText = checkpoint.text;
        compactionSessionFile = String(ctx.sessionManager.getSessionFile?.() || "");
        compactionSessionId = String(ctx.sessionManager.getSessionId?.() || "");
      } catch (error) {
        writeBridgeState(ctx, {
          source: latestSource,
          last_guard: {
            phase,
            ratio,
            threshold,
            action: "checkpoint-failed",
            error: String(error),
          },
        });
        if (ctx.hasUI) {
          ctx.ui.notify(
            `ComfyUI-Pi reached ${(ratio * 100).toFixed(1)}% but could not create the durable checkpoint: ${String(error)}`,
            "warning",
          );
        }
        return false;
      }

      compactionAnchorId = "";
      try {
        const manager = ctx.sessionManager as any;
        if (typeof manager.appendCustomMessageEntry === "function") {
          compactionAnchorId = String(manager.appendCustomMessageEntry(
            "comfyui-pi-compaction-anchor",
            `[ComfyUI-Pi verified compaction anchor]\nDurable checkpoint: ${String(pendingHandoff?.path || "")}\n` +
              "The compaction summary is authoritative continuity state. Continue the same task; do not restart.",
            false,
            { owner: "comfyui-pi", phase, threshold, ratio },
          ) || "");
        }
      } catch {
        compactionAnchorId = "";
      }

      compactionPrepared = true;
      ctx.ui.setStatus(
        "comfyui-pi-compaction",
        phase === "turn-end"
          ? `Checkpoint saved at ${(ratio * 100).toFixed(1)}%; compacting now in the same Pi session...`
          : `Checkpoint saved at ${(ratio * 100).toFixed(1)}%; prepared for same-session compaction...`,
      );
      writeBridgeState(ctx, {
        source: latestSource,
        last_guard: {
          phase,
          ratio,
          threshold,
          action: "compaction-prepared",
          handoff_path: String(pendingHandoff?.path || ""),
          anchor_id: compactionAnchorId,
          session_file: compactionSessionFile,
          session_id: compactionSessionId,
        },
      });
    }

    // Pi's official trigger-compact extension calls ctx.compact() directly from turn_end.
    // That is the correct preemptive boundary: the turn is complete, the durable handoff
    // has been written and anchored, and we have not yet reached Pi's later agent_end
    // automatic-compaction check. Do NOT wait for agent_settled, because a long-running
    // agent loop can keep consuming context until Pi's native overflow compaction wins.
    //
    // agent_end remains prepare-only as a race-avoidance fallback. If context usage was
    // unavailable at turn_end and the checkpoint is first prepared at agent_end, the
    // existing agent_settled hook performs the manual same-session fallback.
    if (phase === "agent-end") return true;
    if (!compactionPrepared) return false;

    compactionRequested = true;
    if (phase !== "turn-end") {
      ctx.ui.setStatus("comfyui-pi-compaction", "Compacting prepared context in place...");
    }
    writeBridgeState(ctx, {
      source: latestSource,
      last_guard: {
        phase,
        ratio,
        threshold,
        action: phase === "turn-end"
          ? "compaction-requested-threshold"
          : "compaction-requested-settled-fallback",
        handoff_path: String(pendingHandoff?.path || ""),
        anchor_id: compactionAnchorId,
        session_file: compactionSessionFile,
        session_id: compactionSessionId,
      },
    });

    try {
      ctx.compact({
        customInstructions: COMFYUI_PI_COMPACTION_INSTRUCTIONS,
        onComplete: () => {
          compactionRequested = false;
          ctx.ui.setStatus("comfyui-pi-compaction", undefined);
        },
        onError: (error) => {
          compactionPrepared = false;
          compactionRequested = false;
          pendingHandoff = undefined;
          pendingHandoffText = "";
          compactionAnchorId = "";
          compactionSessionFile = "";
          compactionSessionId = "";
          ctx.ui.setStatus("comfyui-pi-compaction", undefined);
          ctx.ui.notify(`ComfyUI-Pi compaction failed: ${String(error)}`, "error");
        },
      });
      return true;
    } catch (error) {
      compactionPrepared = false;
      compactionRequested = false;
      pendingHandoff = undefined;
      pendingHandoffText = "";
      compactionAnchorId = "";
      compactionSessionFile = "";
      compactionSessionId = "";
      ctx.ui.setStatus("comfyui-pi-compaction", undefined);
      if (ctx.hasUI) ctx.ui.notify(`ComfyUI-Pi could not start compaction: ${String(error)}`, "error");
      return false;
    }
  };

  pi.on("input", async (event) => {
    if (event.source === "extension") return { action: "continue" };
    latestInput = String(event.text || "");
    latestSource = String(event.source || "interactive");
    const task = latestInput.trim();
    if (task && !task.startsWith("/") && !task.startsWith("!")) {
      activeTaskInput = task;
    }
    return { action: "continue" };
  });

  // Pi remains the compaction authority, but ComfyUI-Pi owns the continuity payload.
  // Native Pi threshold/overflow compaction may arrive between our agent_end preparation
  // and agent_settled. When it does, use the already prepared handoff/anchor. If no
  // checkpoint exists yet, create it here. Never allow a compaction that cannot preserve
  // the durable continuity handoff.
  pi.on("session_before_compact", async (event, ctx) => {
    const configPath = process.env.COMFYUI_PI_BRIDGE_CONFIG || "";
    const config = readJson(configPath);
    if (config.preemptive_handoff === false || !configPath) return undefined;

    const currentSessionFile = String(ctx.sessionManager.getSessionFile?.() || "");
    const currentSessionId = String(ctx.sessionManager.getSessionId?.() || "");
    const requestedByGuard = compactionRequested;
    const handoffReason =
      requestedByGuard && event.reason === "manual" ? "comfyui-threshold" : String(event.reason || "manual");

    if (compactionSessionFile && currentSessionFile && compactionSessionFile !== currentSessionFile) {
      if (ctx.hasUI) {
        ctx.ui.notify(
          "ComfyUI-Pi cancelled compaction because Pi changed session files before the prepared compaction could run.",
          "error",
        );
      }
      return { cancel: true };
    }
    if (compactionSessionId && currentSessionId && compactionSessionId !== currentSessionId) {
      if (ctx.hasUI) {
        ctx.ui.notify(
          "ComfyUI-Pi cancelled compaction because Pi changed session IDs before the prepared compaction could run.",
          "error",
        );
      }
      return { cancel: true };
    }

    if (!pendingHandoff || !pendingHandoffText) {
      try {
        const checkpoint = await createDurableCheckpoint(
          ctx,
          handoffReason,
          Number(event.preparation?.tokensBefore || 0),
        );
        pendingHandoff = checkpoint.metadata;
        pendingHandoffText = checkpoint.text;
        compactionSessionFile = currentSessionFile;
        compactionSessionId = currentSessionId;
        compactionPrepared = true;
      } catch (error) {
        pendingHandoff = undefined;
        pendingHandoffText = "";
        if (ctx.hasUI) {
          ctx.ui.notify(
            `ComfyUI-Pi cancelled ${event.reason} compaction because the durable handoff could not be written: ${String(error)}`,
            "error",
          );
        }
        return { cancel: true };
      }
    }

    const anchored = Boolean(
      compactionAnchorId && branchContainsEntry(event.branchEntries || [], compactionAnchorId)
    );
    const handoffPath = String(pendingHandoff?.path || "");

    // The hidden anchor proves the durable checkpoint was inserted on this branch.
    // It must NOT replace Pi's native recent-message keep boundary. Keeping Pi's
    // firstKeptEntryId preserves the recent user/assistant/tool suffix as designed.
    const firstKeptEntryId = event.preparation.firstKeptEntryId;

    return {
      compaction: {
        summary:
          `${pendingHandoffText}\n\n` +
          `Durable ComfyUI-Pi checkpoint: ${handoffPath}\n` +
          `Preserved Pi session file: ${currentSessionFile}\n` +
          `Preserved Pi session id: ${currentSessionId}`,
        firstKeptEntryId,
        tokensBefore: event.preparation.tokensBefore,
        details: {
          owner: "comfyui-pi",
          handoff_path: handoffPath,
          session_file: currentSessionFile,
          session_id: currentSessionId,
          anchor_id: compactionAnchorId,
          anchored,
          native_first_kept_entry_id: event.preparation.firstKeptEntryId,
        },
      },
    };
  });

  pi.on("session_compact", async (event, ctx) => {
    const requestedByGuard = compactionRequested;
    const handoffPath = String(pendingHandoff?.path || "");
    const summary = String(event.compactionEntry?.summary || "");
    const sessionFileAfter = String(ctx.sessionManager.getSessionFile?.() || "");
    const sessionIdAfter = String(ctx.sessionManager.getSessionId?.() || "");
    const sameSessionFile = !compactionSessionFile || !sessionFileAfter || compactionSessionFile === sessionFileAfter;
    const sameSessionId = !compactionSessionId || !sessionIdAfter || compactionSessionId === sessionIdAfter;
    const sameSession = sameSessionFile && sameSessionId;
    const handoffWasIngested = Boolean(
      handoffPath &&
      summary.includes("Durable ComfyUI-Pi checkpoint:") &&
      summary.includes(handoffPath)
    );

    compactionPrepared = false;
    compactionRequested = false;
    ctx.ui.setStatus("comfyui-pi-compaction", undefined);
    writeBridgeState(ctx, {
      source: "compaction",
      last_compaction: {
        reason: requestedByGuard ? "comfyui-threshold" : event.reason,
        tokens_before: event.compactionEntry?.tokensBefore ?? null,
        first_kept_entry_id: event.compactionEntry?.firstKeptEntryId || "",
        summary_chars: summary.length,
        handoff_path: handoffPath,
        handoff_index: pendingHandoff?.handoff_index ?? null,
        anchor_id: compactionAnchorId,
        summary_source: pendingHandoffText ? "comfyui-durable-handoff" : "pi-native",
        handoff_ingested: handoffWasIngested,
        same_session: sameSession,
        session_file_before: compactionSessionFile,
        session_file_after: sessionFileAfter,
        session_id_before: compactionSessionId,
        session_id_after: sessionIdAfter,
      },
    });

    const taskToResume = activeTaskInput.trim();
    const backup = handoffPath ? ` Durable checkpoint: ${handoffPath}` : "";
    if (!sameSession) {
      ctx.ui.notify(
        "ComfyUI-Pi detected a Pi session change during compaction and blocked automatic continuation.",
        "error",
      );
    } else if (!handoffWasIngested) {
      ctx.ui.notify(
        "Pi compacted in place, but ComfyUI-Pi could not verify that the durable handoff entered the CompactionEntry. Automatic continuation was blocked.",
        "error",
      );
    } else {
      ctx.ui.notify(`Context compacted in place; the exact Pi session was preserved.${backup}`, "info");

      // Overflow recovery already tells Pi to retry the interrupted turn. For normal
      // threshold/manual compaction, schedule one hidden follow-up AFTER the compaction
      // promise unwinds. This starts another agent TURN, never another Pi SESSION.
      if (!event.willRetry && taskToResume) {
        const serial = ++continuationSerial;
        const continuation =
          "[Automatic ComfyUI-Pi continuation after compaction]\n" +
          `Durable handoff already ingested: ${handoffPath}\n` +
          "Continue the exact unfinished user task now from the compacted continuity state. " +
          "Do not ask the user to type continue. Do not start, resume, fork, or switch Pi sessions. " +
          "Do not repeat completed work or restart planning from scratch. " +
          "If the requested task is already complete, return control cleanly.\n\n" +
          "Active user task:\n" + taskToResume.slice(0, 6000);
        setTimeout(() => {
          pi.sendMessage({
            customType: "comfyui-pi-auto-resume",
            content: continuation,
            display: false,
            details: {
              serial,
              handoff_path: handoffPath,
              session_file: sessionFileAfter,
              session_id: sessionIdAfter,
            },
          }, { deliverAs: "followUp", triggerTurn: true });
        }, 0);
      }
    }

    pendingHandoff = undefined;
    pendingHandoffText = "";
    compactionAnchorId = "";
    compactionSessionFile = "";
    compactionSessionId = "";
  });

  pi.on("session_before_switch", async (_event, ctx) => {
    if (!compactionPrepared && !compactionRequested) return undefined;
    if (ctx.hasUI) {
      ctx.ui.notify(
        "ComfyUI-Pi blocked a session switch while compaction continuity is active. Compaction must stay in the current Pi session.",
        "warning",
      );
    }
    return { cancel: true };
  });

  pi.on("session_before_fork", async (_event, ctx) => {
    if (!compactionPrepared && !compactionRequested) return undefined;
    if (ctx.hasUI) {
      ctx.ui.notify(
        "ComfyUI-Pi blocked a session fork while compaction continuity is active.",
        "warning",
      );
    }
    return { cancel: true };
  });

  pi.on("before_agent_start", async (event) => {
    const configPath = process.env.COMFYUI_PI_BRIDGE_CONFIG || "";
    const bridgeModule = process.env.COMFYUI_PI_BRIDGE_MODULE || "comfy_pi_agent.terminal_bridge_cli";
    const python = process.env.COMFYUI_PI_PYTHON || "python3";
    const markerPath = process.env.COMFYUI_PI_HANDOFF_MARKER || "";
    const config = readJson(configPath);
    const text = latestInput;
    latestInput = "";
    if (!text || text.startsWith("/")) return undefined;

    const additions: string[] = [];

    // Backward-compatibility recovery only. Current builds never create this marker because
    // compaction stays in the same Pi session. If an older reset-based build left a marker,
    // ingest it once so that already-lost continuity can still be recovered.
    const handoff = readPendingHandoff(markerPath, Number(config.handoff_max_chars || 8000));
    if (handoff) {
      additions.push(
        "LEGACY COMFYUI-PI CONTINUITY HANDOFF (one-time recovery from an older reset-based build):\n" +
        "Treat this bounded state as authoritative for continuing the user's work. Do not repeat or summarize it to the user. " +
        "Read large referenced files only when needed.\n" +
        `Durable handoff file: ${handoff.path}\n\n${handoff.text}`
      );
      try { unlinkSync(markerPath); } catch {}
    }

    // Do not put an arbitrarily large pasted user prompt in the OS argv. Persist it beside
    // the per-terminal bridge config for the duration of this one routing call instead.
    const inputPath = configPath ? `${configPath}.input` : "";
    try {
      const args = ["-m", bridgeModule];
      if (inputPath) {
        writeFileSync(inputPath, text);
        args.push("--message-file", inputPath);
      } else {
        args.push("--message", text);
      }
      if (config.workflow_path) args.push("--workflow", String(config.workflow_path));
      if (config.project_context) args.push("--project-context", String(config.project_context));
      const result = await pi.exec(python, args);
      const guidance = String(result.stdout || "").trim();
      if (guidance) additions.push(guidance);
    } catch {
      // Dynamic guidance is advisory. Failure must never block the actual Pi terminal.
    } finally {
      if (inputPath) { try { unlinkSync(inputPath); } catch {} }
    }

    if (!additions.length) return undefined;
    return { systemPrompt: event.systemPrompt + "\n\n" + additions.join("\n\n") };
  });

  // Match Pi's official trigger-compact extension: when turn_end crosses the configured
  // threshold, create/verify the durable checkpoint and request ctx.compact() immediately.
  // compactionRequested is set before ctx.compact(), so later lifecycle hooks cannot
  // launch a duplicate compaction while this one is in flight.
  pi.on("turn_end", async (_event, ctx) => {
    await maybeRequestEarlyCompaction(ctx, "turn-end");
  });

  // Pi performs its native automatic-compaction check after extension agent_end handlers.
  // Keep agent_end prepare-only for the unusual case where turn_end usage was unavailable.
  pi.on("agent_end", async (_event, ctx) => {
    writeBridgeState(ctx, { source: latestSource });
    await maybeRequestEarlyCompaction(ctx, "agent-end");
  });

  // Fallback only: if the checkpoint could not be requested from turn_end and Pi did not
  // compact natively, request the already-prepared same-session compaction once settled.
  pi.on("agent_settled", async (_event, ctx) => {
    await maybeRequestEarlyCompaction(ctx, "agent-settled");
  });
}
