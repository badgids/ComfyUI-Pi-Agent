from __future__ import annotations

import shlex
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str
    usage: str
    mode: str = "host"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Pi's documented built-in interactive commands. RPC mode intentionally does not execute
# these when they are sent through `prompt`, so ComfyUI-Pi implements host-side equivalents
# and maps the parts Pi exposes to explicit RPC commands.
BUILTIN_COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand("login", "Manage provider credentials or configure a local server.", "/login [llama.cpp|ollama|lm-studio|vllm|openai-compatible] [url] [model]"),
    SlashCommand("logout", "Explain/remove an active provider selection without exposing secrets.", "/logout [provider]"),
    SlashCommand("llama", "Inspect/configure the llama.cpp router and load, unload, or download router models.", "/llama [url|refresh|load <model>|unload <model>|download <owner/repo:quant>]"),
    SlashCommand("model", "List models or switch the Pi RPC session to a model.", "/model [provider/model | provider model-id | next]"),
    SlashCommand("scoped-models", "Show or set model patterns used for model cycling.", "/scoped-models [comma-separated patterns]"),
    SlashCommand("settings", "Show chat/Pi settings or change supported runtime settings.", "/settings [thinking|steering|follow-up|handoff] [value]"),
    SlashCommand("resume", "List or switch ComfyUI-Pi saved sidebar conversations.", "/resume [chat-session-id]"),
    SlashCommand("new", "Create and switch to a fresh ComfyUI-Pi chat session.", "/new [optional title]"),
    SlashCommand("name", "Set the visible chat/session name.", "/name <name>"),
    SlashCommand("session", "Show current Pi and ComfyUI-Pi session statistics.", "/session"),
    SlashCommand("tree", "Show Pi's current in-memory session tree.", "/tree"),
    SlashCommand("trust", "Show ComfyUI-Pi's supervised project-trust policy.", "/trust"),
    SlashCommand("fork", "List fork points or fork Pi from a user-message entry id.", "/fork [entry-id]"),
    SlashCommand("clone", "Clone Pi's active branch and duplicate the visible sidebar chat.", "/clone"),
    SlashCommand("compact", "Run ComfyUI-Pi's durable handoff/reset compaction now.", "/compact [optional handoff focus]"),
    SlashCommand("copy", "Copy the last assistant reply.", "/copy"),
    SlashCommand("export", "Export the Pi session to HTML.", "/export [output-file]"),
    SlashCommand("import", "Load a Pi JSONL session file into the active RPC process.", "/import <session.jsonl>"),
    SlashCommand("share", "Prepare a safe local export; external sharing remains explicit.", "/share"),
    SlashCommand("reload", "Restart this chat's lean Pi RPC process and reload dynamic configuration.", "/reload"),
    SlashCommand("hotkeys", "Show ComfyUI-Pi chat shortcuts and available slash commands.", "/hotkeys"),
    SlashCommand("changelog", "Show the installed Pi version and ComfyUI-Pi release information.", "/changelog"),
    SlashCommand("quit", "Stop this chat's Pi RPC process without deleting the conversation.", "/quit"),
)

COMMAND_BY_NAME = {item.name: item for item in BUILTIN_COMMANDS}


def command_catalog() -> list[dict[str, Any]]:
    return [item.to_dict() for item in BUILTIN_COMMANDS]


def parse_slash_command(message: str) -> tuple[str, list[str], str] | None:
    text = str(message or "").strip()
    if not text.startswith("/") or text.startswith("//"):
        return None
    first_line = text.splitlines()[0].strip()
    try:
        parts = shlex.split(first_line[1:])
    except ValueError:
        parts = first_line[1:].split()
    if not parts:
        return "", [], ""
    name = parts[0].strip().lower()
    args = parts[1:]
    raw_args = first_line[len(parts[0]) + 1 :].strip()
    return name, args, raw_args


def command_help() -> str:
    rows = ["Pi slash commands available in the ComfyUI-Pi chat:", ""]
    for item in BUILTIN_COMMANDS:
        rows.append(f"- `/{item.name}` — {item.description}")
    rows.extend([
        "",
        "Type `/` in the chat box to filter the command picker. Commands are executed by the ComfyUI-Pi host or mapped to Pi RPC; they are not sent to the LLM as ordinary prompts.",
    ])
    return "\n".join(rows)
