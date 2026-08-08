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
    if (!(ratio > 0) || ratio < threshold) return false;

    // agent_end happens before Pi's own host compaction check. Only PREPARE here.
    // ExtensionContext.compact() is fire-and-forget in Pi 0.83; starting it from
    // agent_end races Pi's subsequent _checkCompaction() and can produce overlapping
    // compactions. The actual early compact request is delayed until agent_settled,
    // after Pi's host compaction decision has finished.
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
        `Checkpoint saved at ${(ratio * 100).toFixed(1)}%; waiting for the safe same-session compaction boundary...`,
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

    if (phase !== "agent-settled") return true;

    // Safe point: Pi's post-agent automatic threshold/overflow check has completed.
    // If Pi already compacted, session_compact cleared compactionPrepared and this
    // function will not be called with prepared state. Otherwise request one manual
    // Pi compaction in the SAME session.
    if (!compactionPrepared) return false;
    compactionRequested = true;
    ctx.ui.setStatus("comfyui-pi-compaction", "Compacting prepared context in place...");
    writeBridgeState(ctx, {
      source: latestSource,
      last_guard: {
        phase,
        ratio,
        threshold,
        action: "compaction-requested-safe",
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
    const firstKeptEntryId = anchored
      ? compactionAnchorId
      : event.preparation.firstKeptEntryId;
    const handoffPath = String(pendingHandoff?.path || "");

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
          anchored,
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
          }, { triggerTurn: true });
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

  // Comfy-Media-Director's proven ordering matters here: Pi performs its host
  // automatic-compaction check after extension agent_end handlers and before
  // agent_settled. Run the configured early guard at agent_end so the durable
  // checkpoint is guaranteed to exist before Pi can compact on its own.
  pi.on("agent_end", async (_event, ctx) => {
    writeBridgeState(ctx, { source: latestSource });
    await maybeRequestEarlyCompaction(ctx, "agent-end");
  });

  // Compatibility fallback. Usually the agent_end gate has already decided whether to
  // compact, but a later settled usage update should still be able to trigger the guard.
  pi.on("agent_settled", async (_event, ctx) => {
    await maybeRequestEarlyCompaction(ctx, "agent-settled");
  });
}
