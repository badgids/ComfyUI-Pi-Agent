/** Dynamic FL-MCP-compatible tool exposure for ComfyUI-Pi.
 *
 * The complete 128-name compatibility catalog lives host-side.  This Pi extension
 * exposes only the tools selected for the current request, plus three tiny discovery
 * controls.  It is safe to load explicitly while Pi's global/project extension discovery
 * is disabled.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const active = new Set<string>();
const descriptions = new Map<string, string>();
const schemas = new Map<string, any>();
const MAX_DYNAMIC_TOOLS = 48;

function pythonExecutable(): string {
  return process.env.COMFYUI_PI_PYTHON || "python3";
}

async function cli(pi: ExtensionAPI, args: string[]): Promise<any> {
  const result = await pi.exec(pythonExecutable(), ["-m", "comfy_pi_agent.mcp.cli", ...args]);
  const raw = String(result.stdout || "").trim();
  if (!raw) throw new Error(String(result.stderr || "ComfyUI-Pi MCP helper returned no output."));
  return JSON.parse(raw);
}

function textResult(value: any) {
  const text = JSON.stringify(value, null, 2);
  return { content: [{ type: "text" as const, text: text.length > 30000 ? text.slice(0, 30000) + "\n… truncated" : text }], details: value };
}

function schemaToTypeBox(schema: any): any {
  if (!schema || typeof schema !== "object") return Type.Any();
  if (Array.isArray(schema.anyOf)) return Type.Union(schema.anyOf.map((item: any) => schemaToTypeBox(item)));
  switch (schema.type) {
    case "string": return Type.String();
    case "integer": return Type.Integer({
      ...(Number.isFinite(schema.minimum) ? { minimum: Number(schema.minimum) } : {}),
      ...(Number.isFinite(schema.maximum) ? { maximum: Number(schema.maximum) } : {}),
    });
    case "number": return Type.Number({
      ...(Number.isFinite(schema.minimum) ? { minimum: Number(schema.minimum) } : {}),
      ...(Number.isFinite(schema.maximum) ? { maximum: Number(schema.maximum) } : {}),
    });
    case "boolean": return Type.Boolean();
    case "array": return Type.Array(schemaToTypeBox(schema.items || {}));
    case "object": {
      const required = new Set(Array.isArray(schema.required) ? schema.required.map(String) : []);
      const properties: Record<string, any> = {};
      for (const [key, value] of Object.entries(schema.properties || {})) {
        const converted = schemaToTypeBox(value);
        properties[key] = required.has(key) ? converted : Type.Optional(converted);
      }
      return Type.Object(properties, { additionalProperties: schema.additionalProperties !== false });
    }
    default: return Type.Any();
  }
}

export function registerDynamicMcpTools(pi: ExtensionAPI) {
  const registerExact = (name: string, description = "ComfyUI-Pi MCP compatibility tool", schema: any = undefined) => {
    const toolName = String(name || "").trim();
    if (!toolName || active.has(toolName) || active.size >= MAX_DYNAMIC_TOOLS) return false;
    try {
      pi.registerTool({
        name: toolName,
        label: toolName,
        description: String(description || descriptions.get(toolName) || "ComfyUI-Pi MCP compatibility tool") +
          " This tool is dynamically exposed from the complete FL-MCP-compatible catalog for the current ComfyUI task.",
        parameters: schemaToTypeBox(schema || schemas.get(toolName) || { type: "object", additionalProperties: true }) as any,
        async execute(_toolCallId, params) {
          try {
            const result = await cli(pi, ["invoke", toolName, "--arguments", JSON.stringify(params || {})]);
            return textResult(result);
          } catch (error) {
            return textResult({ ok: false, tool: toolName, error: String(error) });
          }
        },
      } as any);
      active.add(toolName);
      return true;
    } catch {
      // A host/core extension may already own the same public tool name. Do not replace it.
      return false;
    }
  };

  const activateSpecs = (items: any[]): string[] => {
    const activated: string[] = [];
    for (const item of items || []) {
      if (active.size >= MAX_DYNAMIC_TOOLS) break;
      const name = String(item?.name || "");
      if (!name) continue;
      descriptions.set(name, String(item?.description || ""));
      if (item?.input_schema) schemas.set(name, item.input_schema);
      if (registerExact(name, String(item?.description || ""), item?.input_schema)) activated.push(name);
    }
    return activated;
  };

  const activateNames = async (names: string[]): Promise<string[]> => {
    const wanted = [...new Set((names || []).map(String).filter(Boolean))];
    if (!wanted.length) return [];
    const catalog = await cli(pi, ["catalog"]);
    const byName = new Map((catalog?.tools || []).map((item: any) => [String(item.name), item]));
    return activateSpecs(wanted.map((name) => byName.get(name)).filter(Boolean));
  };

  pi.registerTool({
    name: "comfyui_tool_search",
    label: "Search ComfyUI MCP Tools",
    description:
      "Search ComfyUI-Pi's complete 128-name FL-MCP-compatible tool catalog without exposing the whole catalog to the model. " +
      "Use this when the needed capability is not already visible.",
    parameters: Type.Object({ query: Type.String(), limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 128 })) }),
    async execute(_toolCallId, params) {
      try { return textResult(await cli(pi, ["search", String(params.query || ""), "--limit", String(params.limit || 24)])); }
      catch (error) { return textResult({ ok: false, error: String(error) }); }
    },
  } as any);

  pi.registerTool({
    name: "comfyui_tool_activate",
    label: "Activate ComfyUI MCP Tools",
    description:
      "Dynamically expose exact FL-MCP-compatible ComfyUI tool names or a capability family for this Pi session. " +
      "Use only the smallest set needed for the current task.",
    parameters: Type.Object({ names: Type.Optional(Type.Array(Type.String())), family: Type.Optional(Type.String()) }),
    async execute(_toolCallId, params) {
      try {
        let specs: any[] = [];
        if (String(params.family || "")) specs = (await cli(pi, ["catalog", "--family", String(params.family)])).tools || [];
        const activated = activateSpecs(specs);
        const named = await activateNames(Array.isArray(params.names) ? params.names.map(String) : []);
        return textResult({ ok: true, activated: [...new Set([...activated, ...named])], active_count: active.size, max_dynamic_tools: MAX_DYNAMIC_TOOLS });
      } catch (error) { return textResult({ ok: false, error: String(error) }); }
    },
  } as any);

  pi.registerTool({
    name: "comfyui_tool_call",
    label: "Call ComfyUI MCP Tool",
    description:
      "Immediately invoke any exact FL-MCP-compatible ComfyUI tool by name, even if it has not yet been exposed as a dedicated tool. " +
      "This supports discover-and-call in one model turn while keeping the visible tool list small.",
    parameters: Type.Object({ name: Type.String(), arguments: Type.Optional(Type.Object({}, { additionalProperties: true })) }),
    async execute(_toolCallId, params) {
      const name = String(params.name || "");
      try {
        // Also expose the exact name for subsequent calls in the same session.
        await activateNames([name]);
        return textResult(await cli(pi, ["invoke", name, "--arguments", JSON.stringify(params.arguments || {})]));
      } catch (error) { return textResult({ ok: false, tool: name, error: String(error) }); }
    },
  } as any);

  // Deterministic pre-turn routing: register only the bounded tool subset relevant to
  // the user's current text before Pi begins the agent turn. No LLM is used for routing.
  pi.on("input", async (event) => {
    if (event.source === "extension") return { action: "continue" };
    const text = String(event.text || "").trim();
    if (!text || text.startsWith("/") || text.startsWith("!")) return { action: "continue" };
    try {
      const routed = await cli(pi, ["route-text", text, "--limit", "24"]);
      await activateNames(Array.isArray(routed?.names) ? routed.names.map(String) : []);
    } catch {
      // Routing failure must not prevent Pi from handling the user's message. The three
      // explicit discovery tools remain available so the model/user can recover.
    }
    return { action: "continue" };
  });
}

export default registerDynamicMcpTools;
