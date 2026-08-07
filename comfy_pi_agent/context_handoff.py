from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

from .compat import get_comfy_user_directory
from .io_utils import atomic_write_json

DEFAULT_HANDOFF_THRESHOLD = 0.825
MIN_HANDOFF_THRESHOLD = 0.80
MAX_HANDOFF_THRESHOLD = 0.95
DEFAULT_HANDOFF_MAX_CHARS = 8_000
MIN_HANDOFF_MAX_CHARS = 4_000
MAX_HANDOFF_MAX_CHARS = 16_000


def clamp_threshold(value: float | int | str | None) -> float:
    try:
        number = float(value) if value is not None else DEFAULT_HANDOFF_THRESHOLD
    except (TypeError, ValueError):
        number = DEFAULT_HANDOFF_THRESHOLD
    if number > 1.0:
        number /= 100.0
    return min(MAX_HANDOFF_THRESHOLD, max(MIN_HANDOFF_THRESHOLD, number))


def clamp_handoff_chars(value: int | str | None) -> int:
    try:
        number = int(value) if value is not None else DEFAULT_HANDOFF_MAX_CHARS
    except (TypeError, ValueError):
        number = DEFAULT_HANDOFF_MAX_CHARS
    return min(MAX_HANDOFF_MAX_CHARS, max(MIN_HANDOFF_MAX_CHARS, number))


def calculate_context_tokens(usage: Any) -> int:
    """Mirror Pi's public compaction token calculation.

    Pi prefers usage.totalTokens and otherwise sums input/output/cache counters. The RPC
    payload is JSON, so support the camelCase keys Pi emits as well as common snake_case
    variants used by test doubles or providers.
    """
    if not isinstance(usage, dict):
        return 0

    def number(*keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                return max(0, int(value))
        return 0

    total = number("totalTokens", "total_tokens", "total")
    if total:
        return total
    return (
        number("input", "inputTokens", "input_tokens")
        + number("output", "outputTokens", "output_tokens")
        + number("cacheRead", "cache_read", "cacheReadTokens")
        + number("cacheWrite", "cache_write", "cacheWriteTokens")
    )


@dataclass(frozen=True)
class ContextPressure:
    context_tokens: int
    context_window: int
    ratio: float
    threshold: float
    should_handoff: bool
    source: str = "pi_usage"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def context_pressure(
    usage: Any,
    context_window: int | float | None,
    threshold: float | int | str | None = DEFAULT_HANDOFF_THRESHOLD,
) -> ContextPressure:
    tokens = calculate_context_tokens(usage)
    try:
        window = max(0, int(context_window or 0))
    except (TypeError, ValueError):
        window = 0
    limit = clamp_threshold(threshold)
    ratio = (tokens / window) if tokens > 0 and window > 0 else 0.0
    return ContextPressure(
        context_tokens=tokens,
        context_window=window,
        ratio=ratio,
        threshold=limit,
        should_handoff=bool(window > 0 and tokens > 0 and ratio >= limit),
    )


def _handoff_root(session_id: str) -> Path:
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("Invalid chat session id.")
    root = get_comfy_user_directory() / "pi-agent" / "handoffs" / safe
    root.mkdir(parents=True, exist_ok=True)
    return root


def _section(title: str, value: str) -> str:
    value = str(value or "").strip()
    if not value:
        value = "None recorded."
    return f"## {title}\n{value}\n"


def _bounded_lines(text: str, budget: int) -> str:
    """Trim at line boundaries and preserve both the start and the final next-action area."""
    value = str(text or "").strip()
    if len(value) <= budget:
        return value
    if budget < 500:
        return value[:budget]
    head_budget = int(budget * 0.72)
    tail_budget = budget - head_budget - 80
    head = value[:head_budget].rsplit("\n", 1)[0]
    tail = value[-tail_budget:]
    if "\n" in tail:
        tail = tail.split("\n", 1)[1]
    return head.rstrip() + "\n\n[...middle omitted to keep the handoff compact...]\n\n" + tail.lstrip()


def _recent_visible_history(messages: list[dict[str, Any]], max_chars: int = 6_000) -> str:
    blocks: list[str] = []
    total = 0
    for item in reversed(messages):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        label = "USER" if role == "user" else "ASSISTANT"
        block = f"{label}:\n{content}\n"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 300:
                blocks.append(block[-remaining:])
            break
        blocks.append(block)
        total += len(block)
    blocks.reverse()
    return "\n".join(blocks)


def build_fallback_handoff(
    document: dict[str, Any],
    pressure: ContextPressure,
    project_context: str = "",
    workflow_summary: str = "",
    workflow_context_path: str = "",
    routed_context: dict[str, Any] | None = None,
    max_chars: int = DEFAULT_HANDOFF_MAX_CHARS,
) -> str:
    """Deterministic handoff used if the fresh summarizer process is unavailable."""
    max_chars = clamp_handoff_chars(max_chars)
    messages = document.get("messages") if isinstance(document, dict) else []
    messages = messages if isinstance(messages, list) else []
    integrations = []
    skills = []
    if isinstance(routed_context, dict):
        for item in routed_context.get("loaded_integrations", []) or []:
            if isinstance(item, dict) and item.get("id"):
                integrations.append(str(item["id"]))
        for item in routed_context.get("loaded_skills", []) or []:
            if isinstance(item, dict) and item.get("name"):
                skills.append(str(item["name"]))
    latest_user = next((str(m.get("content") or "").strip() for m in reversed(messages)
                        if isinstance(m, dict) and m.get("role") == "user" and str(m.get("content") or "").strip()), "")
    latest_assistant = next((str(m.get("content") or "").strip() for m in reversed(messages)
                             if isinstance(m, dict) and m.get("role") == "assistant" and str(m.get("content") or "").strip()), "")
    recent = _recent_visible_history(messages, max_chars=4_000)

    header = (
        "# ComfyUI-Pi Continuity Handoff\n\n"
        "> Generated before a ComfyUI-Pi preemptive context reset. This is continuity state, "
        "not a full transcript. Large workflows/assets are referenced by path and should be read only when needed.\n\n"
    )
    body = "".join([
        _section("Primary Objective / Current Request", latest_user),
        _section("Last Agent Result", _bounded_lines(latest_assistant, 1_600)),
        _section("Project Context", _bounded_lines(project_context, 1_200)),
        _section("Current Workflow Digest", _bounded_lines(workflow_summary, 1_500)),
        _section("On-Demand Files", (f"- Full active workflow: `{workflow_context_path}`\n" if workflow_context_path else "") + "Read large files only when the next task requires their exact contents."),
        _section("Dynamic Context To Reload Only If Needed",
                 "Integrations: " + (", ".join(integrations) if integrations else "none")
                 + "\nTask procedures: " + (", ".join(skills) if skills else "none")
                 + "\nReload only procedures/integrations required by the next task; do not preload the library."),
        _section("Recent Visible Conversation", recent),
        _section("Continuation Rules", "- Continue the user's existing work; do not restart from scratch.\n- Preserve user-approved decisions and manually edited artifacts.\n- Re-check live ComfyUI schemas before graph mutations.\n- Load large workflow/project files only when needed.\n- Load third-party node-pack knowledge dynamically, not globally.\n- If information is missing, inspect the referenced project/workflow artifacts before guessing."),
        _section("Context Reset Metadata", f"Context before reset: {pressure.context_tokens:,} / {pressure.context_window:,} tokens ({pressure.ratio * 100:.1f}%).\nTrigger threshold: {pressure.threshold * 100:.1f}%.")
    ])
    return _bounded_lines(header + body, max_chars)


def _handoff_source_payload(
    document: dict[str, Any],
    pressure: ContextPressure,
    project_context: str,
    workflow_summary: str,
    workflow_context_path: str,
    routed_context: dict[str, Any] | None,
) -> dict[str, Any]:
    integrations = []
    skills = []
    if isinstance(routed_context, dict):
        integrations = [
            str(item.get("id")) for item in (routed_context.get("loaded_integrations") or [])
            if isinstance(item, dict) and item.get("id")
        ]
        skills = [
            str(item.get("name")) for item in (routed_context.get("loaded_skills") or [])
            if isinstance(item, dict) and item.get("name")
        ]
    return {
        "purpose": "Source material for a compact continuity handoff. Do not copy the entire transcript into the handoff.",
        "session": {
            "session_id": document.get("session_id"),
            "title": document.get("title"),
            "project_directory": document.get("project_directory"),
            "provider": document.get("provider"),
            "model": document.get("model"),
        },
        "context_pressure": pressure.to_dict(),
        "project_context": str(project_context or "")[:30_000],
        "workflow_summary": str(workflow_summary or "")[:20_000],
        "workflow_context_path": str(workflow_context_path or ""),
        "active_integrations": integrations,
        "active_task_procedures": skills,
        "visible_messages": [
            {"role": m.get("role"), "content": str(m.get("content") or "")}
            for m in (document.get("messages") or []) if isinstance(m, dict) and m.get("role") in {"user", "assistant"}
        ],
    }


REQUIRED_HANDOFF_HEADINGS = (
    "primary objective",
    "next actions",
)


def handoff_is_sufficient(content: str) -> bool:
    """Reject weak/empty handoffs before they become the new session's continuity state."""
    text = str(content or "").strip()
    if len(text) < 250:
        return False
    lowered = text.lower()
    return all(heading in lowered for heading in REQUIRED_HANDOFF_HEADINGS)


class HandoffStore:
    def next_paths(self, session_id: str) -> tuple[int, Path, Path, Path]:
        root = _handoff_root(session_id)
        indexes = []
        for path in root.glob("handoff-*.md"):
            match = re.match(r"handoff-(\d+)\.md$", path.name)
            if match:
                indexes.append(int(match.group(1)))
        index = (max(indexes) + 1) if indexes else 1
        stem = f"handoff-{index:04d}"
        return index, root / f"{stem}.md", root / f"{stem}.json", root / f"{stem}-source.json"

    def create(
        self,
        session_id: str,
        content: str,
        pressure: ContextPressure,
        source_payload: dict[str, Any],
        max_chars: int = DEFAULT_HANDOFF_MAX_CHARS,
        generator: str = "fallback",
    ) -> dict[str, Any]:
        max_chars = clamp_handoff_chars(max_chars)
        content = _bounded_lines(content, max_chars)
        index, md_path, meta_path, source_path = self.next_paths(session_id)
        source_path.write_text(json.dumps(source_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(content.rstrip() + "\n", encoding="utf-8")
        digest = hashlib.sha256(md_path.read_bytes()).hexdigest()
        metadata = {
            "schema_version": 1,
            "session_id": session_id,
            "handoff_index": index,
            "created_at": time.time(),
            "path": str(md_path.resolve()),
            "source_path": str(source_path.resolve()),
            "generator": generator,
            "chars": len(content),
            "sha256": digest,
            "context_pressure": pressure.to_dict(),
        }
        atomic_write_json(meta_path, metadata)
        atomic_write_json(md_path.parent / "latest.json", metadata)
        return metadata


def create_handoff(
    session_id: str,
    document: dict[str, Any],
    pressure: ContextPressure,
    project_context: str = "",
    workflow_summary: str = "",
    workflow_context_path: str = "",
    routed_context: dict[str, Any] | None = None,
    max_chars: int = DEFAULT_HANDOFF_MAX_CHARS,
    summarizer: Callable[[Path, int], str] | None = None,
) -> dict[str, Any]:
    """Create a compact handoff; an optional fresh-process summarizer may improve it.

    `summarizer` receives a temporary JSON source path and the character budget. Keeping the
    summarizer callback outside this module avoids importing/starting Pi just to use the
    deterministic fallback or to inspect handoff files.
    """
    store = HandoffStore()
    source = _handoff_source_payload(
        document, pressure, project_context, workflow_summary, workflow_context_path, routed_context
    )
    # Create source first at the final handoff location so a separate Pi process can read it.
    index, md_path, meta_path, source_path = store.next_paths(session_id)
    source_path.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")

    content = ""
    generator = "fallback"
    if summarizer is not None:
        try:
            content = str(summarizer(source_path, clamp_handoff_chars(max_chars)) or "").strip()
            if handoff_is_sufficient(content):
                generator = "pi_fresh_session"
            else:
                content = ""
        except Exception:
            content = ""
    if not content:
        content = build_fallback_handoff(
            document,
            pressure,
            project_context=project_context,
            workflow_summary=workflow_summary,
            workflow_context_path=workflow_context_path,
            routed_context=routed_context,
            max_chars=max_chars,
        )

    content = _bounded_lines(content, clamp_handoff_chars(max_chars))
    md_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    digest = hashlib.sha256(md_path.read_bytes()).hexdigest()
    # The source payload can contain the complete visible transcript and is needed only by
    # the isolated summarizer. Remove it after the durable compact handoff is written; the
    # canonical sidebar transcript remains in ChatSessionStore.
    try:
        source_path.unlink(missing_ok=True)
        source_retained = False
    except Exception:
        source_retained = True
    metadata = {
        "schema_version": 1,
        "session_id": session_id,
        "handoff_index": index,
        "created_at": time.time(),
        "path": str(md_path.resolve()),
        "source_path": str(source_path.resolve()) if source_retained else "",
        "source_retained": source_retained,
        "generator": generator,
        "chars": len(content),
        "sha256": digest,
        "context_pressure": pressure.to_dict(),
    }
    atomic_write_json(meta_path, metadata)
    atomic_write_json(md_path.parent / "latest.json", metadata)
    return metadata


def handoff_bootstrap_prompt(handoff_path: str, handoff_text: str = "") -> str:
    """Create a deterministic fresh-session bootstrap.

    ComfyUI-Pi normally reads the bounded handoff host-side and embeds it here so even a weak
    model does not need to decide to call a file-read tool. The durable file path is retained
    for later verification and human inspection.
    """
    text = str(handoff_text or "").strip()
    if text:
        return (
            "ComfyUI-Pi performed a preemptive context reset. The bounded continuity handoff "
            "has already been read from disk by the host and is included below. Treat it as "
            "authoritative working state for continuing the user's task. Do not repeat or summarize "
            "it to the user. Large referenced files should still be opened only when needed. "
            "Reply with exactly HANDOFF_READY and nothing else.\n\n"
            f"Durable handoff file: {handoff_path}\n\n"
            "--- BEGIN CONTINUITY HANDOFF ---\n" + text +
            "\n--- END CONTINUITY HANDOFF ---"
        )
    return (
        "ComfyUI-Pi performed a preemptive context reset. Read the continuity handoff file below "
        "exactly once and internalize it as working state. Do not reproduce or summarize it to the "
        "user. Do not read unrelated large files yet. Reply with exactly HANDOFF_READY and nothing else.\n\n"
        f"Handoff file: {handoff_path}"
    )
