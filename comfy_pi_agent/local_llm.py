from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class LocalLLMHTTPError(urllib.error.HTTPError):
    """HTTP error that keeps the local-host endpoint and response body visible."""

    def __init__(self, url: str, code: int, reason: str, headers: Any, body_text: str, method: str) -> None:
        super().__init__(url, code, reason, headers, None)
        self.body_text = str(body_text or "").strip()
        self.method = str(method or "GET").upper()

    def __str__(self) -> str:
        detail = " ".join(self.body_text.split())[:1200]
        suffix = f": {detail}" if detail else f": {self.reason}"
        return f"HTTP {self.code} {self.method} {self.url}{suffix}"


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
    """Return the OpenAI-compatible API root Pi should call for a local server."""
    normalized = _normalize_kind(kind)
    value = normalize_base_url(normalized, base_url)
    if normalized == "ollama":
        return value + "/v1"
    return value if value.endswith("/v1") else value + "/v1"


def local_provider_id(kind: str, provider_id: str = "") -> str:
    """Return the stable Pi provider id for a local-server preset."""
    normalized = _normalize_kind(kind)
    defaults = {
        "llama.cpp": "llama.cpp",
        "ollama": "ollama",
        "lm-studio": "lm-studio",
        "vllm": "vllm",
        "openai-compatible": "comfyui-local",
    }
    requested = str(provider_id or defaults.get(normalized, "comfyui-local")).strip()
    safe = "".join(ch for ch in requested if ch.isalnum() or ch in "._-")
    if not safe:
        raise ValueError("Local provider id is invalid.")
    return safe


def local_provider_presets() -> list[dict[str, str]]:
    """Small UI metadata only; does not contact any local server."""
    return [
        {
            "kind": kind,
            "provider": local_provider_id(kind),
            "label": preset["label"],
            "default_base_url": preset["base_url"],
        }
        for kind, preset in LOCAL_SERVER_PRESETS.items()
    ]


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
    request_method = str(method or "GET").upper()
    request = urllib.request.Request(url, data=body, headers=merged_headers, method=request_method)
    try:
        with urllib.request.urlopen(request, timeout=max(0.25, float(timeout))) as response:
            response_payload = response.read()
    except urllib.error.HTTPError as exc:
        try:
            error_payload = exc.read()
            error_text = error_payload.decode("utf-8", errors="replace") if error_payload else ""
        except Exception:
            error_text = ""
        raise LocalLLMHTTPError(
            url=str(getattr(exc, "url", None) or url),
            code=int(getattr(exc, "code", 0) or 0),
            reason=str(getattr(exc, "reason", None) or getattr(exc, "msg", None) or "HTTP error"),
            headers=getattr(exc, "headers", None),
            body_text=error_text,
            method=request_method,
        ) from exc
    return json.loads(response_payload.decode("utf-8")) if response_payload else {}


def _llama_headers() -> dict[str, str]:
    key = os.environ.get("LLAMA_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _model_entries(payload: Any) -> list[Any]:
    """Return model rows from common OpenAI/Ollama/llama.cpp payload shapes."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "models"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _extract_models(kind: str, payload: Any) -> list[str]:
    normalized = _normalize_kind(kind)
    found: list[str] = []
    for item in _model_entries(payload):
        if isinstance(item, str):
            found.append(item)
            continue
        if not isinstance(item, dict):
            continue
        if normalized == "ollama":
            model_id = item.get("name") or item.get("model") or item.get("id")
        else:
            if normalized == "llama.cpp":
                status = item.get("status") if isinstance(item.get("status"), dict) else {}
                # Router /models is the authoritative catalog. Keep unloaded/sleeping
                # presets; omit only entries the router explicitly says have failed.
                if bool(status.get("failed", False)):
                    continue
            model_id = item.get("id") or item.get("name") or item.get("model")
        if model_id:
            found.append(str(model_id))
    return sorted(dict.fromkeys(found), key=str.lower)


def _looks_like_llama_router_payload(payload: Any) -> bool:
    """Detect router metadata without relying on any user's model names or files."""
    entries = _model_entries(payload)
    return any(
        isinstance(item, dict)
        and ("status" in item or "source" in item or "aliases" in item or "can_remove" in item)
        for item in entries
    )

def probe_local_server(
    kind: str,
    base_url: str = "",
    timeout: float = 2.5,
    reload_catalog: bool = False,
) -> dict[str, Any]:
    """Discover a local host's full model catalog on explicit user action only.

    llama.cpp router mode is handled specially: /models is queried before /v1/models
    because the latter may expose only the currently loaded/default child model. A
    reload is optional and receives a larger timeout because reparsing presets can be
    noticeably slower than an ordinary catalog read.
    """
    normalized = _normalize_kind(kind)
    if normalized not in LOCAL_SERVER_PRESETS:
        normalized = "openai-compatible"
    root = normalize_base_url(normalized, base_url)

    attempts: list[tuple[str, float, str]] = []
    if normalized == "ollama":
        attempts = [(root + "/api/tags", max(1.0, float(timeout)), "native")]
    elif normalized == "llama.cpp":
        router_root = root[:-3].rstrip("/") if root.endswith("/v1") else root
        # Normal sidebar/session refresh uses the router's already-built complete catalog.
        # Explicit Refresh asks llama.cpp to re-read its preset source first; that operation
        # can be slower, so it receives a deliberately larger timeout. If reload fails or
        # times out, fall back to the router's cached full catalog before considering the
        # single-model OpenAI endpoint.
        if reload_catalog:
            attempts.append((router_root + "/models?reload=1", max(15.0, float(timeout)), "router-reload"))
        attempts.append((router_root + "/models", max(2.5, float(timeout)), "router"))
        # Compatibility fallback for a single-model llama-server or older builds that do
        # not expose router metadata. Never prefer this over a successful router catalog.
        attempts.append((router_root + "/v1/models", max(2.5, float(timeout)), "openai"))
    else:
        attempts = [((root if root.endswith("/v1") else root + "/v1") + "/models", max(1.0, float(timeout)), "openai")]

    last_exc: Exception | None = None
    best_empty: dict[str, Any] | None = None
    for probe_url, request_timeout, mode in attempts:
        try:
            headers = _llama_headers() if normalized == "llama.cpp" else None
            payload = _json_request(probe_url, timeout=request_timeout, headers=headers)
            models = _extract_models(normalized, payload)
            router = normalized == "llama.cpp" and _looks_like_llama_router_payload(payload)
            result = {
                "available": True,
                "kind": normalized,
                "provider": local_provider_id(normalized),
                "label": LOCAL_SERVER_PRESETS[normalized]["label"],
                "base_url": root,
                "pi_base_url": openai_base_url(normalized, root),
                "probe_url": probe_url,
                "models": models,
                "router": router,
                "catalog_mode": mode,
                "message": f"Detected {LOCAL_SERVER_PRESETS[normalized]['label']}" + (f" with {len(models)} model(s)." if models else "."),
            }
            if models:
                # Never replace a successful full router catalog with /v1/models.
                return result
            best_empty = best_empty or result
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc

    if best_empty is not None:
        return best_empty
    exc = last_exc or RuntimeError("No model endpoint responded.")
    return {
        "available": False,
        "kind": normalized,
        "provider": local_provider_id(normalized),
        "label": LOCAL_SERVER_PRESETS[normalized]["label"],
        "base_url": root,
        "pi_base_url": openai_base_url(normalized, root),
        "probe_url": attempts[-1][0],
        "models": [],
        "router": False,
        "catalog_mode": "unavailable",
        "message": f"Not detected: {type(exc).__name__}: {exc}",
    }

def llama_router_models(base_url: str = "", reload: bool = False, timeout: float = 5.0) -> dict[str, Any]:
    """Read every model known to a llama.cpp router, including unloaded presets."""
    root = normalize_base_url("llama.cpp", base_url)
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    query = "?reload=1" if reload else ""
    payload = _json_request(
        root + "/models" + query,
        timeout=max(15.0, float(timeout)) if reload else max(2.5, float(timeout)),
        headers=_llama_headers(),
    )
    entries = _model_entries(payload)
    models = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        model_id = str(item.get("id") or item.get("name") or item.get("model") or "")
        if not model_id:
            continue
        models.append({
            "id": model_id,
            "status": str(status.get("value") or "unknown"),
            "failed": bool(status.get("failed", False)),
            "exit_code": status.get("exit_code"),
            "source": str(item.get("source") or ""),
            "aliases": list(item.get("aliases") or []) if isinstance(item.get("aliases"), list) else [],
            "path": str(item.get("path") or ""),
        })
    if not _looks_like_llama_router_payload(payload):
        raise ValueError("The endpoint responded, but it is not a llama.cpp router model catalog.")
    return {"ok": True, "base_url": root, "models": models}


def llama_router_model_tokenize(
    base_url: str,
    model: str,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Send llama.cpp router's lightweight routed tokenize probe to one model.

    Upstream llama.cpp router tests use POST /tokenize with a model id to prove that
    requests are actually reaching the selected child server. This does not generate
    assistant text and does not add anything to Pi's conversation context.
    """
    model_id = str(model or "").strip()
    if not model_id:
        raise ValueError("A llama.cpp model id is required.")
    root = normalize_base_url("llama.cpp", base_url)
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    payload = _json_request(
        root + "/tokenize",
        timeout=max(0.25, float(timeout)),
        method="POST",
        payload={"model": model_id, "content": "ComfyUI-Pi readiness"},
        headers=_llama_headers(),
    )
    if not isinstance(payload, dict):
        raise ValueError("llama.cpp returned an invalid /tokenize response.")
    return payload


def wait_for_llama_server_health(
    base_url: str,
    timeout: float = 180.0,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """Wait for a single-model llama-server's documented /health readiness signal."""
    root = normalize_base_url("llama.cpp", base_url)
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    budget = max(0.1, float(timeout))
    deadline = time.monotonic() + budget
    last_error = "not ready"
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            payload = _json_request(
                root + "/health",
                timeout=min(5.0, remaining),
                headers=_llama_headers(),
            )
            if isinstance(payload, dict) and str(payload.get("status") or "").lower() in {"ok", "ready"}:
                return {"ready": True, "status": str(payload.get("status") or "ok")}
            last_error = str(payload)
        except urllib.error.HTTPError as exc:
            # llama.cpp documents 503 while a single-model server is still loading.
            if int(getattr(exc, "code", 0) or 0) != 503:
                last_error = f"HTTP {getattr(exc, 'code', '?')}"
            else:
                last_error = "HTTP 503: model is still loading"
        except (OSError, TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(min(max(0.1, float(poll_interval)), max(0.1, deadline - time.monotonic())))
    raise TimeoutError(
        f"Timed out after {budget:.0f}s waiting for llama.cpp to become ready (last result: {last_error})."
    )


def wait_for_llama_router_model(
    base_url: str,
    model: str,
    timeout: float = 180.0,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """Wait until one llama.cpp router model can accept a routed task.

    ``unloaded`` presets are explicitly loaded by the caller before this wait begins.
    ``sleeping`` is different: llama.cpp documents that a real incoming task wakes the
    sleeping child automatically, while management/read-only endpoints do not. For a
    sleeping model this function therefore sends the lightweight routed ``/tokenize``
    task immediately and gives that wake request the caller's remaining timeout budget.

    No user-specific timeout is substituted here; ``timeout`` is always the value supplied
    by the caller (normally the sidebar's Timeout in seconds setting).
    """
    model_id = str(model or "").strip()
    if not model_id:
        raise ValueError("A llama.cpp model id is required.")
    budget = max(0.1, float(timeout))
    deadline = time.monotonic() + budget
    last_status = "unknown"
    last_probe = "not attempted"
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        catalog = llama_router_models(base_url, timeout=min(5.0, remaining))
        entry = next((item for item in catalog.get("models", []) if str(item.get("id") or "") == model_id), None)
        if entry is None:
            raise ValueError(f"llama.cpp router no longer reports model '{model_id}'. Refresh the model list.")
        last_status = str(entry.get("status") or "unknown").lower()
        if bool(entry.get("failed", False)):
            detail = f" exit_code={entry.get('exit_code')}" if entry.get("exit_code") is not None else ""
            raise RuntimeError(f"llama.cpp failed to load '{model_id}'.{detail}")

        if last_status in {"loaded", "ready", "sleeping"}:
            # A sleeping llama.cpp child is woken by a real routed task. Give that wake
            # request the full remaining user-configured budget because loading large local
            # models can legitimately take minutes. A loaded child only needs a short probe.
            probe_timeout = remaining if last_status == "sleeping" else min(5.0, remaining)
            try:
                probe = llama_router_model_tokenize(base_url, model_id, timeout=probe_timeout)
                return {
                    "ready": True,
                    "model": model_id,
                    "status": "loaded",
                    "entry": entry,
                    "probe": probe,
                    "woke_from_sleep": last_status == "sleeping",
                }
            except urllib.error.HTTPError as exc:
                code = int(getattr(exc, "code", 0) or 0)
                # Busy/loading conditions can be transient. A 400 is not swallowed: with
                # LocalLLMHTTPError it now includes the exact endpoint and llama.cpp body.
                if code not in {404, 409, 425, 429, 503}:
                    raise
                last_probe = f"/tokenize HTTP {code}"
            except (OSError, TimeoutError) as exc:
                last_probe = f"/tokenize {type(exc).__name__}: {exc}"
        else:
            last_probe = f"router status is {last_status}"

        time.sleep(min(max(0.1, float(poll_interval)), max(0.1, deadline - time.monotonic())))

    raise TimeoutError(
        f"Timed out after {budget:.0f}s waiting for llama.cpp model '{model_id}' to become ready "
        f"(last router status: {last_status}; last readiness probe: {last_probe})."
    )

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
    reload_catalog: bool = False,
) -> dict[str, Any]:
    """Register a discovered local server in Pi's supported models.json catalog.

    All local providers, including llama.cpp, follow the same deterministic path:
    discover models -> merge provider/models into models.json -> restart the supervised
    Pi RPC process -> select provider/model. This avoids relying on a special provider
    path that may not expose the server's model ids to Pi's RPC model snapshot.
    Existing providers and unrelated user settings are preserved. Raw API keys are never
    stored here.
    """
    normalized = _normalize_kind(kind)
    if normalized not in LOCAL_SERVER_PRESETS:
        normalized = "openai-compatible"
    root = normalize_base_url(normalized, base_url)
    requested_models = [str(item).strip() for item in (models or []) if str(item).strip()]
    selected_model = str(model or "").strip()
    discovered_models = not bool(requested_models)

    if not requested_models:
        probe = probe_local_server(normalized, root, reload_catalog=reload_catalog)
        if not probe.get("available"):
            raise ValueError(str(probe.get("message") or "Local server could not be reached."))
        requested_models = list(probe.get("models") or [])
    if selected_model and selected_model not in requested_models:
        if discovered_models:
            # Do not resurrect a stale saved model that the host no longer reports.
            selected_model = ""
        else:
            requested_models.insert(0, selected_model)
    if not selected_model and requested_models:
        selected_model = requested_models[0]
    if not requested_models:
        raise ValueError(
            f"{LOCAL_SERVER_PRESETS[normalized]['label']} is reachable, but it did not report any models. "
            "Load/start a model in that server and try again."
        )

    provider = local_provider_id(normalized, provider_id)
    path = models_json_path()
    data = _read_models_json(path)
    providers = data.setdefault("providers", {})
    env_name = "".join(ch for ch in str(api_key_env or "").strip() if ch.isalnum() or ch == "_")
    # Pi requires configured auth presence before custom models appear as available.
    # Keyless local servers ignore this harmless placeholder.
    api_key_value = f"${env_name}" if env_name else "local"
    providers[provider] = {
        "name": LOCAL_SERVER_PRESETS[normalized]["label"],
        "baseUrl": openai_base_url(normalized, root),
        "api": "openai-completions",
        "apiKey": api_key_value,
        "compat": {
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": False,
        },
        "models": [{"id": item, "name": item} for item in requested_models],
    }
    _atomic_write(path, data)
    return {
        "ok": True,
        "kind": normalized,
        "provider": provider,
        "model": selected_model,
        "base_url": root,
        "pi_base_url": openai_base_url(normalized, root),
        "models": requested_models,
        "models_json": str(path),
        "api_key_env": env_name,
        "message": (
            f"{LOCAL_SERVER_PRESETS[normalized]['label']} is ready for Pi as "
            f"'{provider}/{selected_model}'."
        ),
    }


def runtime_environment(local_config: dict[str, Any] | None) -> dict[str, str]:
    """Return explicit runtime configuration required by Pi's native local providers.

    Pi 0.81+ registers llama.cpp as a built-in provider. The provider is considered
    configured only when its router URL comes from `/login llama.cpp`, stored auth, or
    ``LLAMA_BASE_URL``. ComfyUI-Pi already owns the selected endpoint, so pass that
    endpoint directly to the supervised Pi process instead of requiring a second login.
    Other local providers continue to use the models.json catalog path.
    """
    local = local_config if isinstance(local_config, dict) else {}
    if _normalize_kind(str(local.get("kind") or "")) != "llama.cpp":
        return {}

    root = normalize_base_url("llama.cpp", str(local.get("base_url") or ""))
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    env = {"LLAMA_BASE_URL": root}

    # A raw secret is never persisted in chat/session JSON. If the session names an
    # environment variable containing a router key, copy only its value into the
    # official Pi variable for the child process.
    env_name = "".join(
        ch for ch in str(local.get("api_key_env") or "").strip()
        if ch.isalnum() or ch == "_"
    )
    if env_name:
        api_key = os.environ.get(env_name, "").strip()
        if api_key:
            env["LLAMA_API_KEY"] = api_key
    return env
