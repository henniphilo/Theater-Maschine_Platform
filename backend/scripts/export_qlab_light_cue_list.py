#!/usr/bin/env python3
"""Export QLab light cue numbers from data/light_scenes.json (Kanalübersicht / KI-Stimmungen)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = SCRIPT_ROOT.parent / "tools"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from qlab_light_sim import build_command_text, sim_color_for_scene


def _repo_root() -> Path:
    return SCRIPT_ROOT.parent


def _load_scenes(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenes = payload.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError(f"{path}: expected 'scenes' array")
    return scenes


def export_rows(scenes: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for scene in scenes:
        scene_id = str(scene.get("id") or "").strip()
        if not scene_id:
            continue
        red, green, blue, intensity = sim_color_for_scene(scene)
        from qlab_light_sim import _qlab_level

        channels = scene.get("channels") or []
        groups = scene.get("groups") or []
        rows.append(
            {
                "qlab_cue_number": scene_id,
                "scene_id": scene_id,
                "description": str(scene.get("description") or scene_id),
                "location": str(scene.get("location") or ""),
                "channels": ";".join(str(c) for c in channels),
                "groups": ";".join(str(g) for g in groups),
                "fade_time": str(scene.get("fade_time") or 3.0),
                "sim_red": str(_qlab_level(red)),
                "sim_green": str(_qlab_level(green)),
                "sim_blue": str(_qlab_level(blue)),
                "sim_intensity": str(max(0, min(100, intensity))),
                "command_text": build_command_text(scene).replace("\n", "\\n"),
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "qlab_cue_number",
        "scene_id",
        "description",
        "location",
        "channels",
        "groups",
        "fade_time",
        "sim_red",
        "sim_green",
        "sim_blue",
        "sim_intensity",
        "command_text",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QLab-Licht-Cue-CSV aus light_scenes.json")
    parser.add_argument(
        "--scenes",
        type=Path,
        default=_repo_root() / "data" / "light_scenes.json",
        help="Quelle (Standard: data/light_scenes.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_repo_root() / "data" / "qlab_light_cue_list.csv",
        help="Ziel-CSV",
    )
    args = parser.parse_args(argv)

    scenes_path = args.scenes if args.scenes.is_absolute() else Path.cwd() / args.scenes
    if not scenes_path.is_file():
        print(f"light_scenes.json nicht gefunden: {scenes_path}", file=sys.stderr)
        return 1

    rows = export_rows(_load_scenes(scenes_path))
    out_path = args.out if args.out.is_absolute() else Path.cwd() / args.out
    write_csv(rows, out_path)
    print(f"{len(rows)} Licht-Cues -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
