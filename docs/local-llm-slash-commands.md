# Local LLM servers and Pi slash commands

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Pi Agent sidebar chat](sidebar-chat.md) · [Next: Workflow intelligence](workflow-intelligence.md)
<!-- DOC_NAV_END -->

ComfyUI-Pi's sidebar chat is intended to feel like a normal Pi conversation while remaining inside ComfyUI. You can type Pi's documented slash commands directly into the chat box, and you can point the embedded Pi runtime at a local llama.cpp, Ollama, LM Studio, vLLM, or other OpenAI-compatible server without editing ComfyUI workflows.

## Why ComfyUI-Pi bridges built-in slash commands

Pi's interactive terminal UI owns its built-in commands such as `/model`, `/settings`, `/tree`, and `/compact`. Pi's RPC protocol does **not** execute those built-in TUI commands when they are sent as ordinary prompts. ComfyUI-Pi therefore recognizes the built-in command names itself and maps them to Pi RPC operations or an equivalent ComfyUI-Pi action.

This is deliberate. A slash command should never accidentally become an LLM prompt just because the chat is using RPC mode.

Commands registered by a Pi extension, prompt template, or skill can still be discovered through Pi's RPC command catalog when those resources are explicitly loaded. ComfyUI-Pi continues to start Pi lean by default, so unrelated resources are not loaded simply to populate the command menu.

## Using the slash-command picker

1. Open the **Pi Agent** sidebar.
2. Click in the chat composer.
3. Type `/`.
4. Continue typing to filter the list.
5. Use the mouse, `Up` / `Down`, or `Tab` to choose a command.
6. Add any arguments and press `Enter`.

The chat currently recognizes Pi's documented built-in command names:

| Command | Embedded ComfyUI-Pi behavior |
| --- | --- |
| `/login` | Easy local-server configuration in chat; cloud OAuth remains Pi's interactive credential flow because RPC does not expose the credential selector. |
| `/logout` | Clears this chat's provider/model override. It does not silently delete Pi's stored credentials. |
| `/llama` | Inspect/configure the llama.cpp router and explicitly list, load, unload, refresh, or start downloads for router models. |
| `/model` | List models, select `provider/model`, or cycle to the next model. |
| `/scoped-models` | Show or set the patterns used for model cycling. |
| `/settings` | Show runtime state and change RPC-supported thinking/delivery settings or ComfyUI-Pi's handoff threshold. |
| `/resume` | List or switch persistent ComfyUI-Pi sidebar chats. |
| `/new` | Start a new sidebar chat. |
| `/name` | Rename the current chat and Pi session. |
| `/session` | Show ComfyUI-Pi and Pi session/context statistics. |
| `/tree` | Show Pi's current session tree. |
| `/trust` | Explain the embedded supervised trust policy. ComfyUI-Pi does not silently enable project trust. |
| `/fork` | List fork points or fork from a Pi user-message entry. |
| `/clone` | Clone the current Pi branch and create a matching sidebar chat. |
| `/compact` | Run ComfyUI-Pi's durable handoff/reset now instead of Pi's built-in lossy auto-compaction. |
| `/copy` | Copy the previous assistant answer. |
| `/export` | Export the active Pi session to HTML. |
| `/import` | Load a Pi JSONL session file into the active RPC process. |
| `/share` | Export HTML and, when authenticated GitHub CLI is available, explicitly create a secret gist. |
| `/reload` | Restart the lean Pi RPC process so current model/provider/scoped configuration is re-read. |
| `/hotkeys` | Show the useful ComfyUI-Pi chat keys and slash-command list. |
| `/changelog` | Show the installed Pi version and point to ComfyUI-Pi release notes. |
| `/quit` | Stop Pi for this chat without deleting the saved conversation. |

### Useful examples

```text
/model
/model ollama/qwen2.5-coder:7b
/model next
/settings thinking low
/settings steering one-at-a-time
/scoped-models ollama/*,llama.cpp/*
/session
/tree
/compact Preserve the workflow repair decisions and next unresolved nodes.
```

## Easy local LLM setup

Local-server discovery is **not** performed during ComfyUI startup. Nothing is contacted until you explicitly press a detection button or issue a local-provider command.

### The easiest method

1. Start your local model server normally.
2. Open **Pi Agent → Settings**.
3. Find **Local LLM server**.
4. Press **Detect common servers**.
5. Select the server/model you want.
6. Press **Use in this chat**.
7. Send a message.

ComfyUI-Pi probes these common loopback defaults only when you ask it to detect servers:

| Server | Common default |
| --- | --- |
| llama.cpp | `http://127.0.0.1:8080` |
| Ollama | `http://127.0.0.1:11434` |
| LM Studio | `http://127.0.0.1:1234/v1` |
| vLLM | `http://127.0.0.1:8000/v1` |

For another OpenAI-compatible service, choose **Other OpenAI-compatible**, enter its base URL, press **Check endpoint**, select a discovered model, and then press **Use in this chat**.

### Configure from the chat

Examples:

```text
/llama
/llama http://127.0.0.1:8080
/llama refresh
/llama load my-local-model.gguf
/llama unload my-local-model.gguf
/llama download owner/repository:Q4_K_M
/login ollama
/login ollama http://127.0.0.1:11434
/login lm-studio http://127.0.0.1:1234/v1
/login vllm http://127.0.0.1:8000/v1
```

Successful local `/login` and `/llama load` changes automatically stop the old embedded Pi process; the next normal message starts a fresh Pi RPC process with the selected local provider/model. `/reload` is still available when you explicitly want to restart the process.

`/llama` uses the llama.cpp router's model-management HTTP API only when you issue the command. `/llama download ...` is therefore an explicit request to the user's already-running llama.cpp router to begin that download; ComfyUI-Pi never downloads a model merely because ComfyUI started.

## How provider configuration is stored

### llama.cpp

Pi has a built-in llama.cpp provider. ComfyUI-Pi supplies the selected router URL to the Pi subprocess through `LLAMA_BASE_URL`. It does not create a duplicate custom provider for llama.cpp.

### Ollama, LM Studio, vLLM, and OpenAI-compatible servers

Pi supports custom providers in its `models.json`. When you explicitly press **Use in this chat**, ComfyUI-Pi safely merges the selected provider/models into that file rather than replacing the user's existing providers.

The generated provider uses Pi's broadly compatible `openai-completions` API mode. Compatibility flags disable `developer` messages and `reasoning_effort` for local servers that commonly do not implement those OpenAI features.

## API keys and secrets

Raw API keys are not stored in ComfyUI workflows or ComfyUI-Pi chat JSON.

If a local or LAN OpenAI-compatible endpoint needs authentication:

1. Put the key in an environment variable yourself.
2. In the Local LLM settings, enter only the **environment variable name** in **API-key environment variable**.
3. ComfyUI-Pi writes a `$VARIABLE_NAME` reference into Pi's model configuration.

For ordinary keyless Ollama/local OpenAI-compatible servers, Pi requires a placeholder auth value so the model appears in its catalog; the local server can ignore that placeholder.

## Sparse context is unchanged

Local-provider support does not add server documentation or model lists to every LLM turn.

- Server detection runs only on explicit request.
- The slash-command catalog is host-side UI metadata, not an LLM prompt.
- Built-in slash commands are handled before ComfyUI-Pi's task/integration context router.
- Normal assistant requests keep the existing small operating contract, lazy procedures, workflow digest, and on-demand integration knowledge.
- The 80%–95% preemptive handoff system remains unchanged, with 82.5% as the default.

## Troubleshooting

### No server is detected

Confirm the server is running and listening on the expected host/port. Then choose the server type, enter the endpoint manually, and press **Check endpoint**.

### Server is reachable but no models appear

Make sure a model is actually loaded/available in the server. Ollama model discovery uses its native model-list endpoint; OpenAI-compatible servers use `/v1/models`.

### A newly configured provider does not appear in `/model`

Use `/reload` to restart the lean Pi RPC process, then run `/model` again.

### A cloud `/login` prompt does not open inside ComfyUI

Pi's OAuth/provider credential selector is an interactive terminal UI and is not exposed by the RPC protocol. Authenticate that cloud provider once through normal standalone Pi (or the provider's supported environment variable), then select it inside ComfyUI-Pi with `/model`.

### `/trust` does not enable project resources

That is intentional. The embedded ComfyUI-Pi Pi process keeps its supervised security boundary and does not silently persist project trust decisions. Explicit dynamic integrations and bundled procedures continue to be routed by ComfyUI-Pi itself.

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
