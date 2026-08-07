from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .docx_writer import write_docx
from .io_utils import atomic_write_json, atomic_write_text, load_json, resolve_output_root, safe_join, slugify


def _seconds_to_frames(seconds: float, fps: float) -> int:
    return max(1, round(seconds * fps))


def create_kdenlive_package(manifest_value: str | dict[str, Any], output_directory: str = "", project_name: str = "") -> dict[str, Any]:
    manifest = load_json(manifest_value, default={})
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object.")
    title = project_name.strip() or str(manifest.get("title") or "ComfyUI Production")
    root = resolve_output_root(output_directory, "nle")
    package = safe_join(root, slugify(title))
    package.mkdir(parents=True, exist_ok=True)
    media_dir = safe_join(package, "media")
    media_dir.mkdir(parents=True, exist_ok=True)
    profile = manifest.get("profile", {}) if isinstance(manifest.get("profile"), dict) else {}
    width = int(str(profile.get("width", 1920)).split("x")[0]) if str(profile.get("width", "")).isdigit() else 1920
    height = int(profile.get("height", 1080)) if str(profile.get("height", "")).isdigit() else 1080
    fps_text = str(profile.get("frame_rate", "24/1"))
    try:
        num, den = fps_text.split("/", 1)
        fps = float(num) / float(den)
    except Exception:
        fps = 24.0
        num, den = "24", "1"
    shots = manifest.get("shots", []) if isinstance(manifest.get("shots"), list) else []
    assets_by_id = {str(a.get("asset_id")): a for a in manifest.get("assets", []) if isinstance(a, dict)}
    timeline = []
    cursor = 0
    for index, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            continue
        duration = float(shot.get("duration", 4.0) or 4.0)
        frames = _seconds_to_frames(duration, fps)
        asset = assets_by_id.get(str(shot.get("asset_id")), {})
        source = str(asset.get("path") or shot.get("media_path") or "")
        timeline.append({
            "clip_id": str(shot.get("shot_id") or f"shot-{index:03d}"),
            "source": source,
            "start_frame": cursor,
            "duration_frames": frames,
            "track": "V1",
            "status": "ready" if source else "placeholder"
        })
        cursor += frames
    otio = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": title,
        "metadata": {"comfyui_pi_agent": True, "profile": {"width": width, "height": height, "fps": fps_text}},
        "tracks": {"OTIO_SCHEMA": "Stack.1", "children": [{"OTIO_SCHEMA": "Track.1", "name": "V1 Main Picture", "kind": "Video", "children": timeline}]}
    }
    atomic_write_json(package / f"{slugify(title)}.otio.json", otio)
    atomic_write_json(package / "timeline.json", {"clips": timeline})
    atomic_write_json(package / "project-profile.json", {"width": width, "height": height, "frame_rate": fps_text, "audio_sample_rate": 48000})
    atomic_write_json(package / "media-map.json", {"assets": list(assets_by_id.values())})

    mlt = ET.Element("mlt", {"LC_NUMERIC": "C", "version": "7.0.0", "title": title})
    profile_el = ET.SubElement(mlt, "profile", {
        "description": f"{width}x{height} {fps:.3f} fps", "width": str(width), "height": str(height),
        "progressive": "1", "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": str(width), "display_aspect_den": str(height),
        "frame_rate_num": str(num), "frame_rate_den": str(den), "colorspace": "709"
    })
    playlist = ET.SubElement(mlt, "playlist", {"id": "playlist0"})
    for clip in timeline:
        if clip["source"]:
            producer_id = f"producer_{clip['clip_id']}"
            producer = ET.SubElement(mlt, "producer", {"id": producer_id})
            ET.SubElement(producer, "property", {"name": "resource"}).text = clip["source"]
            ET.SubElement(playlist, "entry", {"producer": producer_id, "in": "0", "out": str(clip["duration_frames"] - 1)})
        else:
            ET.SubElement(playlist, "blank", {"length": str(clip["duration_frames"])})
    tractor = ET.SubElement(mlt, "tractor", {"id": "tractor0", "title": title})
    ET.SubElement(tractor, "track", {"producer": "playlist0"})
    kdenlive_path = package / f"{slugify(title)}.kdenlive"
    ET.ElementTree(mlt).write(kdenlive_path, encoding="utf-8", xml_declaration=True)

    missing = [clip for clip in timeline if not clip["source"]]
    guide = f"""# Assemble {title} in Kdenlive\n\n## Project profile\n\n- Resolution: {width} × {height}\n- Frame rate: {fps_text}\n- Audio: 48 kHz\n\n## Open the project\n\nOpen `{kdenlive_path.name}` in Kdenlive. Keep this package folder together so relative media paths remain easy to repair.\n\n## Timeline\n\n- V1: Main picture\n- Add dialogue, narration, effects, ambience, and music on separate audio tracks.\n\n## Missing or placeholder clips\n\n{len(missing)} timeline entries do not yet have a media path. Replace each blank with the approved generated clip before final export.\n\n## Portable fallback\n\nThe package includes an OTIO-style JSON timeline, `timeline.json`, `media-map.json`, and the project profile. Use those files to rebuild the sequence if the native Kdenlive file is not compatible with your installed Kdenlive version.\n\n## Final checks\n\n1. Relink missing media.\n2. Confirm every scene and shot is in order.\n3. Confirm dialogue and subtitles are synchronized.\n4. Listen for clipping and missing ambience.\n5. Render a short review copy before the final master.\n"""
    atomic_write_text(package / "ASSEMBLE_IN_KDENLIVE.md", guide)
    write_docx(package / "ASSEMBLE_IN_KDENLIVE.docx", guide, "Assemble in Kdenlive")
    return {"package_directory": str(package), "kdenlive_project": str(kdenlive_path), "timeline": timeline, "missing_clips": len(missing)}
