from __future__ import annotations

import json
import mimetypes
import secrets
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


class HttpToolError(RuntimeError):
    def __init__(self, message: str, *, status: int = 0, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def request_json(base_url: str, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None, timeout: float = 30.0, max_bytes: int = 32 * 1024 * 1024) -> Any:
    base = str(base_url or "").rstrip("/") + "/"
    url = urljoin(base, str(path).lstrip("/"))
    if params:
        encoded = urlencode([(k, v) for k, value in params.items() if value is not None for v in (value if isinstance(value, (list, tuple)) else [value])])
        url += ("&" if "?" in url else "?") + encoded
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urlopen(req, timeout=max(0.25, float(timeout))) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise HttpToolError(f"Response exceeds {max_bytes} bytes", status=int(response.status))
            if not raw:
                return {"success": True, "status": int(response.status)}
            content_type = str(response.headers.get("Content-Type") or "")
            if "json" in content_type:
                return json.loads(raw.decode("utf-8"))
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {"success": True, "status": int(response.status), "text": raw.decode("utf-8", errors="replace")}
    except HTTPError as exc:
        raw = exc.read(max_bytes)
        try:
            detail: Any = json.loads(raw.decode("utf-8"))
        except Exception:
            detail = raw.decode("utf-8", errors="replace")
        raise HttpToolError(f"{method.upper()} {path} failed with HTTP {exc.code}: {detail}", status=int(exc.code), body=detail) from exc
    except URLError as exc:
        raise HttpToolError(f"Could not reach ComfyUI at {base_url}: {exc.reason}") from exc


def request_bytes(base_url: str, method: str, path: str, *, params: dict[str, Any] | None = None, timeout: float = 30.0, max_bytes: int = 64 * 1024 * 1024) -> tuple[bytes, str]:
    base = str(base_url or "").rstrip("/") + "/"
    url = urljoin(base, str(path).lstrip("/"))
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    req = Request(url, method=method.upper())
    try:
        with urlopen(req, timeout=max(0.25, float(timeout))) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise HttpToolError(f"Response exceeds {max_bytes} bytes", status=int(response.status))
            return raw, str(response.headers.get("Content-Type") or "application/octet-stream")
    except HTTPError as exc:
        raise HttpToolError(f"{method.upper()} {path} failed with HTTP {exc.code}", status=int(exc.code)) from exc
    except URLError as exc:
        raise HttpToolError(f"Could not reach ComfyUI at {base_url}: {exc.reason}") from exc


def upload_file(base_url: str, path: str, file_path: str | Path, *, field: str = "file", fields: dict[str, Any] | None = None, timeout: float = 60.0) -> Any:
    source = Path(file_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(str(source))
    boundary = "----ComfyUIPi" + secrets.token_hex(12)
    chunks: list[bytes] = []
    for key, value in (fields or {}).items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"), b"\r\n",
        ])
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; filename="{source.name}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        source.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode(),
    ])
    data = b"".join(chunks)
    url = str(base_url).rstrip("/") + "/" + str(path).lstrip("/")
    req = Request(url, data=data, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=max(1.0, float(timeout))) as response:
            raw = response.read(32 * 1024 * 1024)
            return json.loads(raw.decode("utf-8")) if raw else {"success": True, "status": int(response.status)}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HttpToolError(f"Upload failed with HTTP {exc.code}: {detail}", status=int(exc.code), body=detail) from exc
