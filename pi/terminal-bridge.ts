/**
 * ComfyUI-Pi terminal bridge.
 *
 * This is the single explicitly loaded Pi extension used by Terminal mode. It keeps
 * startup sparse and injects only task-specific ComfyUI/node-pack guidance when a user
 * actually submits a prompt. The visible text in Pi remains the user's original input.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "fs";

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
  let latestInput = "";
  let latestSource = "interactive";
  let compactionRequested = false;
  let pendingHandoff: any = undefined;

  pi.on("input", async (event) => {
    if (event.source === "extension") return { action: "continue" };
    latestInput = String(event.text || "");
    latestSource = String(event.source || "interactive");
    return { action: "continue" };
  });

  // Pi remains the compaction authority. Before *any* Pi compaction (manual, threshold,
  // overflow, or our earlier configured guard) create ComfyUI-Pi's bounded durable
  // checkpoint, then return undefined so Pi appends its normal CompactionEntry and rebuilds
  // the current session from the summary + kept recent messages. Never cancel and never /new.
  pi.on("session_before_compact", async (event, ctx) => {
    const configPath = process.env.COMFYUI_PI_BRIDGE_CONFIG || "";
    const config = readJson(configPath);
    pendingHandoff = undefined;
    if (config.preemptive_handoff === false || !configPath) return undefined;

    const sessionFile = String(ctx.sessionManager.getSessionFile?.() || "");
    if (!sessionFile) return undefined;
    const usage = ctx.getContextUsage?.();
    const contextWindow = Number(usage?.contextWindow || ctx.model?.contextWindow || 0);
    const tokensBefore = Number(event.preparation?.tokensBefore || usage?.tokens || 0);
    const handoffReason =
      compactionRequested && event.reason === "manual" ? "comfyui-threshold" : String(event.reason || "manual");
    const bridgeModule = process.env.COMFYUI_PI_BRIDGE_MODULE || "comfy_pi_agent.terminal_bridge_cli";
    const python = process.env.COMFYUI_PI_PYTHON || "python3";

    try {
      const result = await pi.exec(python, [
        "-m", bridgeModule,
        "--create-handoff",
        "--config", configPath,
        "--session-file", sessionFile,
        "--context-tokens", String(tokensBefore),
        "--context-window", String(contextWindow),
        "--reason", handoffReason,
      ]);
      const text = String(result.stdout || "").trim();
      if (text) pendingHandoff = JSON.parse(text);
    } catch {
      // A durable backup is additive. Failure to write it must never cancel Pi's own
      // compaction, because native compaction is the active continuity mechanism.
      pendingHandoff = undefined;
    }
    return undefined;
  });

  pi.on("session_compact", async (event, ctx) => {
    const requestedByGuard = compactionRequested;
    compactionRequested = false;
    ctx.ui.setStatus("comfyui-pi-compaction", undefined);
    writeBridgeState(ctx, {
      source: "compaction",
      last_compaction: {
        reason: requestedByGuard ? "comfyui-threshold" : event.reason,
        tokens_before: event.compactionEntry?.tokensBefore ?? null,
        first_kept_entry_id: event.compactionEntry?.firstKeptEntryId || "",
        summary_chars: String(event.compactionEntry?.summary || "").length,
        handoff_path: String(pendingHandoff?.path || ""),
        handoff_index: pendingHandoff?.handoff_index ?? null,
      },
    });
    const backup = pendingHandoff?.path ? ` Durable checkpoint: ${pendingHandoff.path}` : "";
    ctx.ui.notify(`Context compacted in place; the current Pi session was preserved.${backup}`, "info");
    pendingHandoff = undefined;
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

  pi.on("agent_end", async (_event, ctx) => {
    writeBridgeState(ctx, { source: latestSource });
  });

  // Pi's own threshold/overflow checks have already run when agent_settled fires. If the
  // configured ComfyUI-Pi threshold is intentionally earlier than Pi's normal reserve-token
  // threshold, request Pi's public in-place compactor here. This avoids racing Pi's own
  // automatic compaction while preserving the user's 80-95% configurable guard.
  pi.on("agent_settled", async (_event, ctx) => {
    if (compactionRequested) return;
    const config = readJson(process.env.COMFYUI_PI_BRIDGE_CONFIG || "");
    if (config.preemptive_handoff === false) return;
    const usage = ctx.getContextUsage?.();
    const ratio = normalizedRatio(usage?.percent, usage?.tokens, usage?.contextWindow);
    let threshold = Number(config.handoff_threshold || 0.825);
    if (threshold > 1) threshold /= 100;
    threshold = Math.max(0.80, Math.min(0.95, threshold));
    if (!usage?.tokens || !usage?.contextWindow || ratio < threshold) return;

    compactionRequested = true;
    ctx.ui.setStatus(
      "comfyui-pi-compaction",
      `Compacting context in place at ${(ratio * 100).toFixed(1)}%...`,
    );
    ctx.compact({
      customInstructions: COMFYUI_PI_COMPACTION_INSTRUCTIONS,
      onComplete: () => {
        compactionRequested = false;
        ctx.ui.setStatus("comfyui-pi-compaction", undefined);
      },
      onError: (error) => {
        compactionRequested = false;
        ctx.ui.setStatus("comfyui-pi-compaction", undefined);
        ctx.ui.notify(`ComfyUI-Pi compaction failed: ${String(error)}`, "error");
      },
    });
  });
}
