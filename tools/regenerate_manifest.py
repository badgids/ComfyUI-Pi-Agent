#!/usr/bin/env python3
"""Regenerate MANIFEST.json from the exact release checkout.

The integrity manifest deliberately excludes itself. It includes tracked files and
non-ignored untracked files so a newly added release file is not silently omitted
when the maintainer regenerates the manifest immediately after applying a patch.
Run this only from a release checkout without unrelated untracked files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "MANIFEST.json"
VERSION_PATH = ROOT / "comfy_pi_agent" / "version.py"
EXCLUDED_PATHS = {"MANIFEST.json"}


def package_version() -> str:
    text = VERSION_PATH.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not read __version__ from {VERSION_PATH}")
    return match.group(1)


def release_paths() -> list[str]:
    command = [
        "git",
        "-C",
        str(ROOT),
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    ]
    try:
        output = subprocess.run(command, check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("MANIFEST generation requires a Git checkout.") from exc

    paths: set[str] = set()
    for raw in output.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8")
        if path in EXCLUDED_PATHS:
            continue
        file_path = ROOT / path
        if file_path.is_file():
            paths.add(path)
    return sorted(paths)


def file_record(relative_path: str) -> dict[str, object]:
    path = ROOT / relative_path
    data = path.read_bytes()
    return {
        "path": relative_path,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_manifest() -> dict[str, object]:
    records = [file_record(path) for path in release_paths()]
    return {
        "schema_version": "1.0",
        "project": "ComfyUI Pi Agent Production Suite",
        "version": package_version(),
        "creator": "Alan D. Guice (Badgids)",
        "license": "GPL-3.0-only",
        "file_count": len(records),
        "files": records,
    }


def encoded_manifest() -> str:
    return json.dumps(build_manifest(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if MANIFEST.json does not match the exact current checkout",
    )
    args = parser.parse_args()

    rendered = encoded_manifest()
    if args.check:
        if not MANIFEST_PATH.is_file():
            print("MANIFEST.json is missing.", file=sys.stderr)
            return 1
        current = MANIFEST_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(
                "MANIFEST.json is stale. Run: python tools/regenerate_manifest.py",
                file=sys.stderr,
            )
            return 1
        print(f"MANIFEST.json is current for ComfyUI-Pi {package_version()}.")
        return 0

    MANIFEST_PATH.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {MANIFEST_PATH.name}: version {package_version()}, "
        f"{build_manifest()['file_count']} files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
