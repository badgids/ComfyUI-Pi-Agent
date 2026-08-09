from __future__ import annotations

import html
import ipaddress
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = str(dict(attrs).get("href") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._href = ""

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)
            if self._href:
                self.links.append((text, self._href))


def _safe_public(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only absolute public HTTP(S) URLs are allowed.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The web URL has an invalid port.") from exc
    if port and port not in {80, 443}:
        raise ValueError("Only standard public HTTP(S) ports are allowed.")
    for info in socket.getaddrinfo(
        parsed.hostname,
        port or (443 if parsed.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    ):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(
                "Private, loopback, link-local, multicast, and metadata targets are blocked."
            )


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Validate every redirect target before urllib is allowed to request it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        target = urljoin(req.full_url, str(newurl))
        _safe_public(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


_OPENER = build_opener(_SafeRedirectHandler())


def _fetch(url: str, max_bytes: int = 2_000_000) -> tuple[str, str]:
    _safe_public(url)
    req = Request(
        url,
        headers={
            "User-Agent": "ComfyUI-Pi-Agent/1.0",
            "Accept": "text/html,text/plain;q=0.9",
        },
    )
    with _OPENER.open(req, timeout=20) as response:
        final = response.geturl()
        _safe_public(final)
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("Web response exceeded the size limit.")
        ctype = str(response.headers.get("Content-Type") or "")
        if not ("text/" in ctype or "html" in ctype):
            raise ValueError(f"Unsupported web content type: {ctype}")
        return raw.decode("utf-8", errors="replace"), final


async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    if name == "web_fetch_page":
        text, final = _fetch(
            str(p.get("url") or ""),
            max(1000, min(int(p.get("max_bytes", 2_000_000) or 2_000_000), 5_000_000)),
        )
        parser = _Text()
        parser.feed(text)
        links = []
        for label, href in parser.links[:200]:
            target = urljoin(final, href)
            try:
                _safe_public(target)
            except (OSError, ValueError):
                continue
            links.append({"text": label, "url": target})
        return {
            "url": final,
            "text": "\n".join(parser.parts)[:200000],
            "links": links,
        }
    if name == "web_search":
        q = str(p.get("query") or "").strip()
        limit = max(1, min(int(p.get("limit", 10) or 10), 20))
        text, _ = _fetch("https://html.duckduckgo.com/html/?q=" + quote_plus(q))
        parser = _Text()
        parser.feed(text)
        results: list[dict[str, str]] = []
        for title, href in parser.links:
            if "uddg=" not in href and not href.startswith("http"):
                continue
            if href.startswith("//duckduckgo.com/l/?"):
                target = parse_qs(urlsplit("https:" + href).query).get("uddg", [""])[0]
            else:
                target = href
            if not target or not title:
                continue
            try:
                _safe_public(target)
            except (OSError, ValueError):
                continue
            if all(item["url"] != target for item in results):
                results.append({"title": html.unescape(title), "url": target})
            if len(results) >= limit:
                break
        return {
            "query": q,
            "results": results,
            "count": len(results),
            "provider": "duckduckgo-html",
        }
    raise KeyError(name)
