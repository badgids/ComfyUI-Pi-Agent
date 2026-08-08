from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .markdown_diagrams import (
    create_comfyui_v2_node_markdown,
    create_flowchart_markdown,
)


def _request(path: str) -> dict[str, Any]:
    value = Path(path).expanduser()
    if not value.is_file():
        raise FileNotFoundError(f"Request file does not exist: {value}")
    data = json.loads(value.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Diagram request must be a JSON object.")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="ComfyUI-Pi deterministic Markdown diagram helper")
    parser.add_argument("mode", choices=("flowchart", "node"))
    parser.add_argument("--request", required=True)
    args = parser.parse_args()

    request = _request(args.request)
    if args.mode == "flowchart":
        result = create_flowchart_markdown(
            markdown_path=str(request.get("markdown_path") or ""),
            spec=request.get("spec") if isinstance(request.get("spec"), dict) else {},
            diagram_id=str(request.get("diagram_id") or "flowchart"),
            alt_text=str(request.get("alt_text") or "Flowchart"),
            include_ascii=bool(request.get("include_ascii", True)),
            ascii_text=str(request.get("ascii_text") or ""),
        )
    else:
        result = create_comfyui_v2_node_markdown(
            markdown_path=str(request.get("markdown_path") or ""),
            base_url=str(request.get("comfyui_base_url") or ""),
            workflow_path=str(request.get("workflow_path") or ""),
            node_id=str(request.get("node_id") or ""),
            node_type=str(request.get("node_type") or ""),
            image_id=str(request.get("image_id") or ""),
            alt_text=str(request.get("alt_text") or ""),
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
