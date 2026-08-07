# Local LLM servers and Pi slash commands

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Real Pi terminal](pi-terminal.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_END -->


ComfyUI-Pi's default sidebar Terminal is the real interactive Pi CLI, so Pi slash commands use Pi's native implementation. The secondary structured Chat keeps host-side bridges for the same documented command names. Local servers are selected from a normal provider dropdown instead of requiring users to understand Pi provider IDs, environment plumbing, or `models.json`.

## Provider and Model are on the main sidebar

Directly beneath the active Terminal/Chat interaction area, ComfyUI-Pi shows:

```text
Provider  [ ... ]
Model     [ ... ]
```

**Provider always comes first. Model always comes second.** You do not need to open Settings just to switch providers or models.

The Provider dropdown has four groups:

- **Default** — Pi's normal configured/current model.
- **Local model hosts** — llama.cpp, Ollama, LM Studio, vLLM, and a generic OpenAI-compatible server.
- **Pi built-in providers** — every provider ID in the Pi `KnownProvider` catalog supported by this release.
- **Custom providers** — provider IDs found in the user's Pi `models.json` or live Pi model catalog.

For built-in/cloud providers, ComfyUI-Pi asks Pi for its live `get_available_models` snapshot and shows every returned model for the selected provider. The model names are **not** duplicated in a plugin hardcoded list. A provider can therefore remain visible while its Model dropdown is empty when Pi has no currently authenticated/configured model for it.

### Pi built-in providers covered by this release

The dropdown covers the 40 provider IDs in Pi's current public `KnownProvider` catalog:

`amazon-bedrock`, `ant-ling`, `anthropic`, `google`, `google-vertex`, `openai`, `azure-openai-responses`, `openai-codex`, `radius`, `nvidia`, `deepseek`, `github-copilot`, `xai`, `groq`, `cerebras`, `openrouter`, `vercel-ai-gateway`, `zai`, `zai-coding-cn`, `mistral`, `minimax`, `minimax-cn`, `moonshotai`, `moonshotai-cn`, `huggingface`, `fireworks`, `together`, `baseten`, `opencode`, `opencode-go`, `kimi-coding`, `cloudflare-workers-ai`, `cloudflare-ai-gateway`, `qwen-token-plan`, `qwen-token-plan-cn`, `qwen-token-plan-individual`, `xiaomi`, `xiaomi-token-plan-cn`, `xiaomi-token-plan-ams`, and `xiaomi-token-plan-sgp`.

The local-host entries are additional convenience providers managed by ComfyUI-Pi. Runtime/custom providers are unioned into the selector so a user-defined provider does not disappear just because it is not in that built-in list.

## Local models: the normal workflow

For llama.cpp, Ollama, LM Studio, vLLM, and generic OpenAI-compatible servers:

1. Start the local server.
2. Beneath the active Terminal/Chat view, choose the host from **Provider**.
3. ComfyUI-Pi contacts only that selected host using its common default endpoint.
4. It reads the host's model list, registers those model IDs with Pi, and fills **Model**.
5. Choose any model in **Model** and use the chat.

That is the normal setup. There is no required **Pi provider ID**, no manual `models.json` editing, and no **Use in this chat** button.

### What “all local models” means

ComfyUI-Pi uses each host's own model-list API rather than guessing filenames:

- **Ollama:** every model returned by `/api/tags`.
- **LM Studio:** every model returned by its OpenAI-compatible `/v1/models`.
- **vLLM:** every model returned by its OpenAI-compatible `/v1/models`.
- **Other OpenAI-compatible:** every model returned by `/v1/models`.
- **llama.cpp single-model server:** the served model from `/v1/models`.
- **llama.cpp router:** every non-failed model returned by the router's live `/models` catalog, including presets currently marked unloaded or sleeping. The ordinary sidebar refresh uses this fast full catalog. The explicit **Refresh models / apply endpoint** button asks `/models?reload=1` to re-read the router preset source with a longer timeout, then falls back to the cached full `/models` catalog if that reload is slow or unavailable. It does not collapse to `/v1/models` after a valid router catalog is available.

A model explicitly marked failed by the llama.cpp router is not offered as a normal selectable model because the host itself says that entry failed to load. ComfyUI-Pi does not inspect a user's private llama.cpp INI file or hardcode preset names; the running router is the authority for what exists.

### Default endpoints

| Provider | Automatic default |
| --- | --- |
| llama.cpp | `http://127.0.0.1:8080` |
| Ollama | `http://127.0.0.1:11434` |
| LM Studio | `http://127.0.0.1:1234/v1` |
| vLLM | `http://127.0.0.1:8000/v1` |
| Other OpenAI-compatible | `http://127.0.0.1:8000/v1` |

The endpoint is an **override, not a required setting**. Leave it alone when the server uses its normal address.

When a server runs somewhere else, select that local provider, open **Settings → Local model host — advanced → Advanced: custom endpoint**, enter the endpoint, then press **Refresh models / apply endpoint**.

No local endpoint is probed during ComfyUI startup. A probe occurs only after the user explicitly selects or refreshes a local provider.

## What ComfyUI-Pi does automatically

ComfyUI-Pi manages the local model catalog in `~/.pi/agent/models.json`. Current Pi also ships `llama.cpp` as a native built-in provider, and that provider has one additional requirement: the router connection itself must be configured by `/login llama.cpp`, stored auth, or Pi's documented `LLAMA_BASE_URL` environment variable.

When ComfyUI-Pi launches a supervised Terminal/RPC process with llama.cpp selected, it supplies the selected endpoint as `LLAMA_BASE_URL`. If the saved local configuration references an API-key environment variable, its value is supplied to the child as `LLAMA_API_KEY`. This means the embedded Pi process is configured directly from the endpoint the user selected in ComfyUI; loading a model in llama.cpp alone is not treated as provider configuration.

After selecting llama.cpp with a server reporting a model such as `example-model`, ComfyUI-Pi also creates or safely merges a model-catalog entry equivalent to:

```json
{
  "providers": {
    "llama.cpp": {
      "name": "llama.cpp",
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "local",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [
        { "id": "example-model", "name": "example-model" }
      ]
    }
  }
}
```

Existing unrelated Pi providers are preserved. The harmless `local` key is only a configured-auth placeholder for keyless local servers; raw secrets are not stored by ComfyUI-Pi.

Ollama, LM Studio, vLLM, and generic OpenAI-compatible providers use this `models.json` configuration as their provider definition. llama.cpp keeps the catalog entry for ComfyUI-Pi model selection while the native Pi provider receives its router connection through `LLAMA_BASE_URL`. Pi must know both the model ID and, for native llama.cpp, how to reach the router before inference can start.

When a local host's registered model catalog changes, ComfyUI-Pi closes only that chat's supervised Pi RPC process so Pi reloads the updated `models.json`. ComfyUI itself does not need to restart. For llama.cpp router models, selecting or sending with an unloaded model first requests `/models/load` when needed and **waits until the router reports the model ready** before Pi is launched or switched. This prevents the first chat request from racing a long model load. Ordinary switching between provider/models that Pi already reports as available uses live RPC `set_model` and keeps the active Pi process/context.

## llama.cpp readiness and startup diagnostics

llama.cpp router `/models/load` is asynchronous. ComfyUI-Pi does not treat its HTTP response—or a `sleeping` router row—as proof that inference is ready. Unloaded or sleeping models are explicitly loaded/woken, the router catalog is polled until the selected model reports `loaded`, and a lightweight model-targeted `POST /tokenize` must succeed before Pi is started or switched. This mirrors llama.cpp's own router tests and does not generate assistant text. The **user-configured chat timeout** is passed through as the complete model-readiness budget; ComfyUI-Pi does not substitute a machine-specific timeout. Single-model llama-server instances use the documented `/health` endpoint and wait through HTTP 503 while the model is loading.

Only after readiness succeeds does ComfyUI-Pi launch its supervised Pi RPC process. Pi RPC startup is separately probed with `get_state`; if Pi exits during startup, the chat error now includes the recent Pi stderr lines and process exit code instead of only `Pi exited before accepting the command`.

Restoring the Pi Agent sidebar or bottom panel is intentionally passive. Collapsing and reopening the interface does not probe the local host, rewrite provider configuration, restart Pi, or create a new session. Saved model rows are restored immediately; use **Refresh models / apply endpoint** when you explicitly want to re-probe the host or reload its catalog.

The Provider and Model native selects also receive explicit dark-mode colors for the select, option, and optgroup elements so the expanded menus remain readable in ComfyUI's dark UI.

## `/model` is forgiving for local providers

These are both valid:

```text
/model llama.cpp
/model llama.cpp/example-model
```

`/model llama.cpp` means **switch this chat to the llama.cpp provider**. ComfyUI-Pi discovers/registers its available models and selects the previous model for that provider when possible, otherwise the first available model.

It is no longer interpreted as “find a model named `llama.cpp` under whatever provider was previously active.” Endpoint URLs are also rejected/repaired as provider IDs, which prevents malformed combinations such as:

```text
http://127.0.0.1:8080/llama.cpp
```

Other examples:

```text
/model ollama
/model ollama/qwen3:8b
/model lm-studio
/model vllm
/model next
/model
```

## llama.cpp router commands

The normal Provider/Model dropdowns are enough to use llama.cpp. Router mode exposes all non-failed routable models in the Model dropdown; selecting an unloaded model requests the load and waits for the router to report it ready before Pi uses it. The `/llama` commands remain optional explicit router-management tools:

```text
/llama
/llama refresh
/llama load <model-id>
/llama unload <model-id>
/llama download <owner/repository:quant>
```

`/llama load` also registers and selects the loaded model for the current ComfyUI-Pi chat. These router operations are never performed automatically at startup.

## Pi slash commands in Terminal and Chat

In **Terminal**, these are the actual Pi interactive slash commands and Pi owns their menus, selectors, and behavior. In **Chat**, ComfyUI-Pi keeps compatibility bridges for the documented command names because Pi explicitly treats many built-in TUI commands as interactive-only rather than RPC prompts.


Pi's interactive terminal owns many built-in slash commands. Sending those names as ordinary text through RPC does not reproduce the TUI behavior, so ComfyUI-Pi recognizes the built-in names before the LLM/context router and maps them to Pi RPC operations or safe ComfyUI equivalents.

Type `/` in the composer to open the command picker. Continue typing to filter it. Arrow keys and Tab can select an entry.

| Command | Embedded behavior |
| --- | --- |
| `/login` | Local-provider convenience command; cloud OAuth still uses Pi's supported external credential flow when RPC cannot expose the TUI selector. |
| `/logout` | Clears this chat's provider/model override without silently deleting Pi credentials. |
| `/llama` | Optional llama.cpp router model management. |
| `/model` | Lists models, switches provider/model, or cycles models. Local provider names can be used alone. |
| `/scoped-models` | Shows or changes model-cycle patterns. |
| `/settings` | Shows/changes RPC-supported settings and handoff threshold. |
| `/resume` | Lists/switches saved ComfyUI-Pi chats. |
| `/new` | Starts a new sidebar chat. |
| `/name` | Renames the chat/Pi session. |
| `/session` | Shows Pi session/context statistics. |
| `/tree` | Displays Pi session-tree information in chat. |
| `/trust` | Explains the supervised trust boundary; it does not silently enable project trust. |
| `/fork` | Lists or uses Pi fork points. |
| `/clone` | Clones the active Pi branch/chat state. |
| `/compact` | Runs ComfyUI-Pi's durable preemptive handoff/reset rather than Pi's built-in compactor. |
| `/copy` | Copies the previous assistant answer. |
| `/export` | Exports the Pi session to HTML. |
| `/import` | Loads a Pi JSONL session. |
| `/share` | Creates a local export and can explicitly share via authenticated `gh`. |
| `/reload` | Restarts only the lean Pi RPC process. |
| `/hotkeys` | Shows chat shortcuts and command help. |
| `/changelog` | Shows installed Pi version/release-note location. |
| `/quit` | Stops Pi for the chat without deleting the conversation. |

## Authentication and secrets

Most local servers are keyless. Nothing extra is required.

For llama.cpp, the selected endpoint is passed to the supervised Pi process as `LLAMA_BASE_URL`. If the saved local configuration names an environment variable containing a router key, ComfyUI-Pi maps that value to Pi's `LLAMA_API_KEY` only in the child process; the raw key is not written into the chat/session JSON.

For an authenticated generic OpenAI-compatible endpoint, expand **Advanced: custom endpoint** and provide the **environment-variable name** that contains the key. ComfyUI-Pi stores a `$VARIABLE_NAME` reference in Pi's configuration, not the raw key.

## Sparse context behavior is unchanged

Provider/model discovery is host-side configuration, not LLM context.

- No local server is contacted at plugin import/startup.
- Model lists are not injected into ordinary LLM turns.
- Slash commands are intercepted before workflow/integration/task-procedure context is built.
- Node-pack integrations remain lazy.
- The 80%–95% preemptive-handoff range remains unchanged, with 82.5% as the default.

## Troubleshooting

### Selecting llama.cpp reports no models

Confirm llama.cpp is running and exposes a model through single-model `/v1/models` or router `/models`. Router mode does **not** require a model to already be loaded; unloaded routable models are listed too. The common default is `http://127.0.0.1:8080`. Expand **Advanced: custom endpoint** only when yours differs.

### The server is on a different host or port

Select the provider, expand **Advanced: custom endpoint**, enter the actual endpoint, and press **Refresh models / apply endpoint**.

### Pi says `Provider is not configured: llama.cpp`

A loaded llama.cpp model and a reachable router are not, by themselves, Pi provider configuration. Pi's native llama.cpp provider requires the router URL from `/login llama.cpp`, stored auth, or `LLAMA_BASE_URL`. ComfyUI-Pi supplies the selected endpoint as `LLAMA_BASE_URL` when it launches its supervised Pi process, so the embedded terminal does not require a separate login. Fully restart ComfyUI after updating the plugin so the Python server uses the updated runtime environment code.

### An old chat contains a URL in its provider field

v0.1.10 and later repair the old malformed v0.1.9 state by deriving the provider from the saved local-server kind. Selecting the provider again writes the corrected state.

### `/model llama.cpp` used to fail

v0.1.9 discovered llama.cpp models but did not register them in Pi's available-model catalog. v0.1.10 uses the same supported Pi `models.json` mechanism for llama.cpp as the other local OpenAI-compatible servers, so Pi can resolve `llama.cpp/<model-id>` correctly.

## Related guides

- [Pi Agent sidebar chat](sidebar-chat.md)
- [Pi runtime and model-provider setup](pi-runtime.md)
- [Small local model reliability](small-model-reliability.md)
- [Dynamic integration context](dynamic-integration-context.md)
- [Preemptive context handoff](context-handoff.md)
- [Security and path policy](security.md)

<!-- DOC_NAV_FOOTER_START -->
---
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Real Pi terminal](pi-terminal.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_FOOTER_END -->

### Sleeping llama.cpp router models

A llama.cpp router can keep a model entry in `sleeping` state after idle sleep. ComfyUI-Pi treats that differently from `unloaded`: only an unloaded preset is sent to `/models/load`. A sleeping model is woken by a lightweight routed `/tokenize` task, because llama.cpp defines real incoming tasks as the wake trigger. The wait uses the current chat's configured **Timeout in seconds** value; no personal timeout value is hardcoded. HTTP failures include the method, endpoint, status, and response body for troubleshooting.
