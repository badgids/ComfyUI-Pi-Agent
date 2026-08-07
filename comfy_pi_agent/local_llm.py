from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


LOCAL_SERVER_PRESETS: dict[str, dict[str, str]] = {
    "llama.cpp": {
        "label": "llama.cpp",
        "base_url": "http://127.0.0.1:8080",
        "probe_path": "/v1/models",
    },
    "ollama": {
        "label": "Ollama",
        "base_url": "http://127.0.0.1:11434",
        "probe_path": "/api/tags",
    },
    "lm-studio": {
        "label": "LM Studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "probe_path": "/models",
    },
    "vllm": {
        "label": "vLLM",
        "base_url": "http://127.0.0.1:8000/v1",
        "probe_path": "/models",
    },
    "openai-compatible": {
        "label": "OpenAI-compatible server",
        "base_url": "http://127.0.0.1:8000/v1",
        "probe_path": "/models",
    },
}


def _normalize_kind(kind: str) -> str:
    value = str(kind or "").strip().lower()
    aliases = {
        "llamacpp": "llama.cpp",
        "llama-cpp": "llama.cpp",
        "llama_cpp": "llama.cpp",
        "lmstudio": "lm-studio",
        "lm_studio": "lm-studio",
        "openai": "openai-compatible",
        "generic": "openai-compatible",
    }
    return aliases.get(value, value)


def _strip_trailing_slash(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def default_base_url(kind: str) -> str:
    normalized = _normalize_kind(kind)
    return LOCAL_SERVER_PRESETS.get(normalized, LOCAL_SERVER_PRESETS["openai-compatible"])["base_url"]


def normalize_base_url(kind: str, base_url: str = "") -> str:
    normalized = _normalize_kind(kind)
    value = _strip_trailing_slash(base_url or default_base_url(normalized))
    if normalized in {"ollama"}:
        # Ollama's native discovery endpoint is rooted at /api, while Pi speaks to /v1.
        if value.endswith("/v1"):
            value = value[:-3].rstrip("/")
    return value


def openai_base_url(kind: str, base_url: str = "") -> str:
    normalized = _normalize_kind(kind)
    value = normalize_base_url(normalized, base_url)
    if normalized == "llama.cpp":
        # Pi has a first-class llama.cpp provider and expects the router root URL.
        return value[:-3].rstrip("/") if value.endswith("/v1") else value
    if normalized == "ollama":
        return value + "/v1"
    return value if value.endswith("/v1") else value + "/v1"


def _json_request(
    url: str,
    timeout: float = 1.25,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    merged_headers = {"Accept": "application/json", "User-Agent": "ComfyUI-Pi-Agent"}
    merged_headers.update(headers or {})
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=merged_headers, method=str(method or "GET").upper())
    with urllib.request.urlopen(request, timeout=max(0.25, float(timeout))) as response:
        response_payload = response.read()
    return json.loads(response_payload.decode("utf-8")) if response_payload else {}


def _llama_headers() -> dict[str, str]:
    key = os.environ.get("LLAMA_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _extract_models(kind: str, payload: Any) -> list[str]:
    normalized = _normalize_kind(kind)
    found: list[str] = []
    if normalized == "ollama" and isinstance(payload, dict):
        for item in payload.get("models") or []:
            if isinstance(item, dict):
                model_id = item.get("name") or item.get("model")
                if model_id:
                    found.append(str(model_id))
    elif normalized == "llama.cpp" and isinstance(payload, dict):
        for item in payload.get("data") or []:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            status_value = str(status.get("value") or "") if isinstance(status, dict) else ""
            # Router /models contains unloaded entries; only loaded/sleeping models are
            # ready for Pi when router autoload is disabled. Single-model responses have
            # no router status and are therefore usable as-is.
            if status_value and status_value not in {"loaded", "sleeping"}:
                continue
            model_id = item.get("id") or item.get("name") or item.get("model")
            if model_id:
                found.append(str(model_id))
    elif isinstance(payload, dict):
        for item in payload.get("data") or payload.get("models") or []:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name") or item.get("model")
                if model_id:
                    found.append(str(model_id))
            elif isinstance(item, str):
                found.append(item)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name") or item.get("model")
                if model_id:
                    found.append(str(model_id))
            elif isinstance(item, str):
                found.append(item)
    return sorted(dict.fromkeys(found), key=str.lower)


def probe_local_server(kind: str, base_url: str = "", timeout: float = 1.25) -> dict[str, Any]:
    normalized = _normalize_kind(kind)
    if normalized not in LOCAL_SERVER_PRESETS:
        normalized = "openai-compatible"
    root = normalize_base_url(normalized, base_url)
    if normalized == "ollama":
        probe_url = root + "/api/tags"
    elif normalized == "llama.cpp":
        probe_url = (root[:-3].rstrip("/") if root.endswith("/v1") else root) + "/models"
    else:
        probe_url = (root if root.endswith("/v1") else root + "/v1") + "/models"
    try:
        payload = _json_request(probe_url, timeout=timeout)
        models = _extract_models(normalized, payload)
        return {
            "available": True,
            "kind": normalized,
            "label": LOCAL_SERVER_PRESETS[normalized]["label"],
            "base_url": root,
            "pi_base_url": openai_base_url(normalized, root),
            "probe_url": probe_url,
            "models": models,
            "message": f"Detected {LOCAL_SERVER_PRESETS[normalized]['label']}" + (f" with {len(models)} model(s)." if models else "."),
        }
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "kind": normalized,
            "label": LOCAL_SERVER_PRESETS[normalized]["label"],
            "base_url": root,
            "pi_base_url": openai_base_url(normalized, root),
            "probe_url": probe_url,
            "models": [],
            "message": f"Not detected: {type(exc).__name__}: {exc}",
        }


def llama_router_models(base_url: str = "", reload: bool = False, timeout: float = 2.0) -> dict[str, Any]:
    root = normalize_base_url("llama.cpp", base_url)
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    query = "?reload=1" if reload else ""
    payload = _json_request(root + "/models" + query, timeout=timeout, headers=_llama_headers())
    entries = payload.get("data") if isinstance(payload, dict) else []
    entries = entries if isinstance(entries, list) else []
    models = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        models.append({
            "id": str(item.get("id") or item.get("name") or item.get("model") or ""),
            "status": str(status.get("value") or "unknown"),
            "failed": bool(status.get("failed", False)),
            "path": str(item.get("path") or ""),
        })
    return {"ok": True, "base_url": root, "models": models}


def llama_router_action(
    action: str,
    model: str,
    base_url: str = "",
    timeout: float = 10.0,
) -> dict[str, Any]:
    operation = str(action or "").strip().lower()
    if operation not in {"load", "unload", "download"}:
        raise ValueError("llama.cpp router action must be load, unload, or download.")
    model_id = str(model or "").strip()
    if not model_id:
        raise ValueError(f"Usage: `/llama {operation} <model-id>`")
    root = normalize_base_url("llama.cpp", base_url)
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    endpoint = "/models" if operation == "download" else f"/models/{operation}"
    result = _json_request(
        root + endpoint,
        timeout=timeout,
        method="POST",
        payload={"model": model_id},
        headers=_llama_headers(),
    )
    return {"ok": bool(result.get("success", True)) if isinstance(result, dict) else True, "action": operation, "model": model_id, "base_url": root, "response": result}


def discover_local_servers(timeout: float = 0.75) -> list[dict[str, Any]]:
    """Probe common loopback endpoints only when explicitly requested by the UI/API."""
    results = []
    for kind in ("llama.cpp", "ollama", "lm-studio", "vllm"):
        results.append(probe_local_server(kind, timeout=timeout))
    return results


def pi_agent_config_directory() -> Path:
    configured = os.environ.get("PI_CODING_AGENT_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".pi" / "agent"


def models_json_path() -> Path:
    return pi_agent_config_directory() / "models.json"


def _read_models_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"providers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Pi models.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Pi models.json must contain a JSON object.")
    data.setdefault("providers", {})
    if not isinstance(data["providers"], dict):
        raise ValueError("Pi models.json 'providers' must be an object.")
    return data


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass


def configure_local_provider(
    kind: str,
    base_url: str = "",
    models: list[str] | None = None,
    model: str = "",
    provider_id: str = "",
    api_key_env: str = "",
) -> dict[str, Any]:
    """Configure Pi for a local server without storing a raw API key.

    llama.cpp is a Pi built-in provider and only needs LLAMA_BASE_URL at process launch.
    Ollama/LM Studio/vLLM/generic OpenAI-compatible servers are merged into Pi's models.json.
    Existing providers and unrelated user settings are preserved.
    """
    normalized = _normalize_kind(kind)
    if normalized not in LOCAL_SERVER_PRESETS:
        normalized = "openai-compatible"
    root = normalize_base_url(normalized, base_url)
    requested_models = [str(item).strip() for item in (models or []) if str(item).strip()]
    selected_model = str(model or "").strip()
    if selected_model and selected_model not in requested_models:
        requested_models.insert(0, selected_model)

    if normalized == "llama.cpp":
        return {
            "ok": True,
            "kind": normalized,
            "provider": "llama.cpp",
            "model": selected_model or (requested_models[0] if requested_models else ""),
            "base_url": root,
            "models": requested_models,
            "models_json": "",
            "message": "llama.cpp configured for this ComfyUI-Pi chat. Pi will receive LLAMA_BASE_URL when its RPC process starts.",
        }

    if not requested_models:
        probe = probe_local_server(normalized, root)
        requested_models = list(probe.get("models") or [])
    if selected_model and selected_model not in requested_models:
        requested_models.insert(0, selected_model)
    if not selected_model and requested_models:
        selected_model = requested_models[0]
    if not requested_models:
        raise ValueError("No local models were supplied or discovered. Start the server/load a model, then detect again.")

    default_provider_ids = {
        "ollama": "ollama",
        "lm-studio": "lm-studio",
        "vllm": "vllm",
        "openai-compatible": "comfyui-local",
    }
    provider = str(provider_id or default_provider_ids[normalized]).strip()
    safe_provider = "".join(ch for ch in provider if ch.isalnum() or ch in "._-")
    if not safe_provider:
        raise ValueError("Local provider id is invalid.")

    path = models_json_path()
    data = _read_models_json(path)
    providers = data.setdefault("providers", {})
    env_name = "".join(ch for ch in str(api_key_env or "").strip() if ch.isalnum() or ch == "_")
    api_key_value = f"${env_name}" if env_name else ("ollama" if normalized == "ollama" else "local")
    providers[safe_provider] = {
        "baseUrl": openai_base_url(normalized, root),
        "api": "openai-completions",
        "apiKey": api_key_value,
        "compat": {
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": False,
        },
        "models": [{"id": item} for item in requested_models],
    }
    _atomic_write(path, data)
    return {
        "ok": True,
        "kind": normalized,
        "provider": safe_provider,
        "model": selected_model,
        "base_url": root,
        "models": requested_models,
        "models_json": str(path),
        "api_key_env": env_name,
        "message": f"Configured Pi provider '{safe_provider}' in models.json without storing a raw API key.",
    }


def runtime_environment(local_config: dict[str, Any] | None) -> dict[str, str]:
    config = local_config if isinstance(local_config, dict) else {}
    kind = _normalize_kind(str(config.get("kind") or ""))
    base_url = str(config.get("base_url") or "").strip()
    if kind == "llama.cpp" and base_url:
        return {"LLAMA_BASE_URL": openai_base_url(kind, base_url)}
    return {}
