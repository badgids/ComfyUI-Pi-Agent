/**
 * ComfyUI-Pi terminal bridge.
 *
 * This is the single explicitly loaded Pi extension used by Terminal mode. It keeps
 * startup sparse and injects only task-specific ComfyUI/node-pack guidance when a user
 * actually submits a prompt. The visible text in Pi remains the user's original input.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "fs";

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

export default function comfyUiPiTerminalBridge(pi: ExtensionAPI) {
  let latestInput = "";
  let latestSource = "interactive";

  pi.on("input", async (event) => {
    if (event.source === "extension") return { action: "continue" };
    latestInput = String(event.text || "");
    latestSource = String(event.source || "interactive");
    return { action: "continue" };
  });

  // ComfyUI-Pi owns threshold-based compaction so it can make a durable handoff first.
  // Manual /compact remains a real Pi command, and overflow recovery remains available as
  // an emergency fallback if a single turn grows beyond the model context unexpectedly.
  pi.on("session_before_compact", async (event) => {
    const config = readJson(process.env.COMFYUI_PI_BRIDGE_CONFIG || "");
    if (event.reason === "threshold" && config.preemptive_handoff !== false) {
      return { cancel: true };
    }
    return undefined;
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
    const handoff = readPendingHandoff(markerPath, Number(config.handoff_max_chars || 8000));
    if (handoff) {
      additions.push(
        "COMFYUI-PI CONTINUITY HANDOFF (host-injected once after a preemptive context reset):\n" +
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
    const statePath = process.env.COMFYUI_PI_BRIDGE_STATE || "";
    if (!statePath) return;
    const usage = ctx.getContextUsage?.();
    const sessionFile = ctx.sessionManager.getSessionFile?.();
    const payload = {
      updated_at: Date.now() / 1000,
      source: latestSource,
      context_tokens: usage?.tokens ?? null,
      context_window: usage?.contextWindow ?? 0,
      context_percent: usage?.percent ?? null,
      session_file: sessionFile || "",
      session_id: ctx.sessionManager.getSessionId?.() || "",
    };
    try { writeFileSync(statePath, JSON.stringify(payload, null, 2)); } catch {}
  });
}
