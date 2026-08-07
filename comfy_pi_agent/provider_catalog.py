from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .local_llm import local_provider_presets, models_json_path


# Keep this list aligned with Pi's public KnownProvider union in
# packages/ai/src/types.ts. The UI also unions these ids with providers that
# Pi reports at runtime, so newly available/custom providers do not disappear
# merely because this plugin has not released an update yet.
PI_BUILTIN_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("amazon-bedrock", "Amazon Bedrock"),
    ("ant-ling", "Ant Ling"),
    ("anthropic", "Anthropic"),
    ("google", "Google Gemini"),
    ("google-vertex", "Google Vertex AI"),
    ("openai", "OpenAI"),
    ("azure-openai-responses", "Azure OpenAI Responses"),
    ("openai-codex", "OpenAI Codex (ChatGPT Plus/Pro)"),
    ("radius", "Radius"),
    ("nvidia", "NVIDIA NIM"),
    ("deepseek", "DeepSeek"),
    ("github-copilot", "GitHub Copilot"),
    ("xai", "xAI"),
    ("groq", "Groq"),
    ("cerebras", "Cerebras"),
    ("openrouter", "OpenRouter"),
    ("vercel-ai-gateway", "Vercel AI Gateway"),
    ("zai", "ZAI Coding Plan (Global)"),
    ("zai-coding-cn", "ZAI Coding Plan (China)"),
    ("mistral", "Mistral"),
    ("minimax", "MiniMax"),
    ("minimax-cn", "MiniMax (China)"),
    ("moonshotai", "Moonshot AI"),
    ("moonshotai-cn", "Moonshot AI (China)"),
    ("huggingface", "Hugging Face"),
    ("fireworks", "Fireworks"),
    ("together", "Together AI"),
    ("opencode", "OpenCode Zen"),
    ("opencode-go", "OpenCode Go"),
    ("kimi-coding", "Kimi For Coding"),
    ("cloudflare-workers-ai", "Cloudflare Workers AI"),
    ("cloudflare-ai-gateway", "Cloudflare AI Gateway"),
    ("qwen-token-plan", "Qwen Token Plan"),
    ("qwen-token-plan-cn", "Qwen Token Plan (China)"),
    ("xiaomi", "Xiaomi MiMo"),
    ("xiaomi-token-plan-cn", "Xiaomi MiMo Token Plan (China)"),
    ("xiaomi-token-plan-ams", "Xiaomi MiMo Token Plan (Amsterdam)"),
    ("xiaomi-token-plan-sgp", "Xiaomi MiMo Token Plan (Singapore)"),
)

PI_BUILTIN_PROVIDER_IDS = frozenset(provider_id for provider_id, _label in PI_BUILTIN_PROVIDERS)


def configured_provider_ids(path: Path | None = None) -> list[str]:
    """Return only provider ids from Pi models.json; never expose credentials/settings."""
    config_path = path or models_json_path()
    if not config_path.exists():
        return []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    providers = payload.get("providers") if isinstance(payload, dict) else {}
    if not isinstance(providers, dict):
        return []
    return sorted(
        {str(provider_id).strip() for provider_id in providers if str(provider_id).strip()},
        key=str.lower,
    )


def _runtime_provider_ids(models: list[dict[str, Any]] | None) -> list[str]:
    found: set[str] = set()
    for item in models or []:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or item.get("providerId") or "").strip()
        if provider:
            found.add(provider)
    return sorted(found, key=str.lower)


def provider_options(models: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Return provider selector metadata without probing local servers.

    The list always contains every provider in Pi's current KnownProvider union,
    the supported local-host presets, and any custom/runtime provider ids that are
    visible in the user's Pi configuration or available-model snapshot.
    """
    options: list[dict[str, str]] = [
        {
            "selector": "pi-default",
            "provider": "",
            "label": "Pi default / current configured model",
            "source": "default",
        }
    ]
    seen_selectors = {"pi-default"}
    seen_provider_ids: set[str] = set()

    for item in local_provider_presets():
        selector = str(item.get("kind") or "").strip()
        provider_id = str(item.get("provider") or "").strip()
        if not selector or selector in seen_selectors:
            continue
        options.append({
            "selector": selector,
            "provider": provider_id,
            "label": str(item.get("label") or selector),
            "source": "local",
            "default_base_url": str(item.get("default_base_url") or ""),
        })
        seen_selectors.add(selector)
        if provider_id:
            seen_provider_ids.add(provider_id)

    for provider_id, label in PI_BUILTIN_PROVIDERS:
        if provider_id in seen_provider_ids:
            continue
        options.append({
            "selector": provider_id,
            "provider": provider_id,
            "label": label,
            "source": "builtin",
        })
        seen_selectors.add(provider_id)
        seen_provider_ids.add(provider_id)

    extra_ids = set(configured_provider_ids()) | set(_runtime_provider_ids(models))
    for provider_id in sorted(extra_ids, key=str.lower):
        if provider_id in seen_provider_ids or provider_id in seen_selectors:
            continue
        options.append({
            "selector": provider_id,
            "provider": provider_id,
            "label": provider_id,
            "source": "custom",
        })
        seen_selectors.add(provider_id)
        seen_provider_ids.add(provider_id)

    return options


def simplified_models(models: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return a stable, UI-safe model catalog with no auth/headers/provider secrets."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in models or []:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or item.get("providerId") or "").strip()
        model_id = str(item.get("id") or item.get("modelId") or item.get("name") or "").strip()
        if not provider or not model_id:
            continue
        key = (provider, model_id)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "provider": provider,
            "id": model_id,
            "name": str(item.get("name") or model_id),
            "reasoning": bool(item.get("reasoning", False)),
            "context_window": int(item.get("contextWindow") or 0) if str(item.get("contextWindow") or "").isdigit() else 0,
            "max_tokens": int(item.get("maxTokens") or 0) if str(item.get("maxTokens") or "").isdigit() else 0,
        })
    result.sort(key=lambda row: (str(row["provider"]).lower(), str(row["name"]).lower(), str(row["id"]).lower()))
    return result
