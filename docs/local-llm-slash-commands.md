# Local LLM servers and Pi slash commands

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar chat](sidebar-chat.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_END -->


ComfyUI-Pi's sidebar chat is intended to make Pi feel like a normal assistant inside ComfyUI. Pi slash commands work from the chat box, and local servers are selected from a normal provider dropdown instead of requiring users to understand Pi provider IDs, environment plumbing, or `models.json`.

## Provider and Model are on the main chat page

Directly beneath the chat box, ComfyUI-Pi shows:

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

### Pi built-in providers covered by v0.1.11

The dropdown covers the 38 provider IDs in Pi's current public `KnownProvider` catalog:

`amazon-bedrock`, `ant-ling`, `anthropic`, `google`, `google-vertex`, `openai`, `azure-openai-responses`, `openai-codex`, `radius`, `nvidia`, `deepseek`, `github-copilot`, `xai`, `groq`, `cerebras`, `openrouter`, `vercel-ai-gateway`, `zai`, `zai-coding-cn`, `mistral`, `minimax`, `minimax-cn`, `moonshotai`, `moonshotai-cn`, `huggingface`, `fireworks`, `together`, `opencode`, `opencode-go`, `kimi-coding`, `cloudflare-workers-ai`, `cloudflare-ai-gateway`, `qwen-token-plan`, `qwen-token-plan-cn`, `xiaomi`, `xiaomi-token-plan-cn`, `xiaomi-token-plan-ams`, and `xiaomi-token-plan-sgp`.

The local-host entries are additional convenience providers managed by ComfyUI-Pi. Runtime/custom providers are unioned into the selector so a user-defined provider does not disappear just because it is not in that built-in list.

## Local models: the normal workflow

For llama.cpp, Ollama, LM Studio, vLLM, and generic OpenAI-compatible servers:

1. Start the local server.
2. Under the chat box, choose the host from **Provider**.
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
- **llama.cpp router:** every non-failed model returned by router `/models?reload=1`, including models currently marked unloaded. llama.cpp router normally autoloads a requested model; ComfyUI-Pi also makes a best-effort `/models/load` request when an unloaded router model is selected so switching still works when router autoload was disabled.

A model explicitly marked failed by the llama.cpp router is not offered as a normal selectable model because the host itself says that entry failed to load.

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

Pi supports custom/local models through `~/.pi/agent/models.json`. ComfyUI-Pi manages that integration for the user.

After selecting llama.cpp with a server reporting `Qwen3.6-35B`, ComfyUI-Pi creates or safely merges an entry equivalent to:

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
        { "id": "Qwen3.6-35B", "name": "Qwen3.6-35B" }
      ]
    }
  }
}
```

Existing unrelated Pi providers are preserved. The harmless `local` key is only a configured-auth placeholder for keyless local servers; raw secrets are not stored by ComfyUI-Pi.

The same mechanism is used for Ollama, LM Studio, vLLM, and generic OpenAI-compatible providers. This unified path is important: Pi must actually know the local model ID before its RPC `set_model` operation can select it.

When a local host's registered model catalog changes, ComfyUI-Pi closes only that chat's supervised Pi RPC process so Pi reloads the updated `models.json`. ComfyUI itself does not need to restart. Ordinary switching between provider/models that Pi already reports as available uses live RPC `set_model` and keeps the active Pi process/context.

## `/model` is forgiving for local providers

These are both valid:

```text
/model llama.cpp
/model llama.cpp/Qwen3.6-35B
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

The normal Provider/Model dropdowns are enough to use llama.cpp. Router mode exposes all non-failed routable models in the Model dropdown and selected unloaded models receive a best-effort load request. The `/llama` commands remain optional explicit router-management tools:

```text
/llama
/llama refresh
/llama load <model-id>
/llama unload <model-id>
/llama download <owner/repository:quant>
```

`/llama load` also registers and selects the loaded model for the current ComfyUI-Pi chat. These router operations are never performed automatically at startup.

## Pi slash commands in the ComfyUI chat

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
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar chat](sidebar-chat.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_FOOTER_END -->
