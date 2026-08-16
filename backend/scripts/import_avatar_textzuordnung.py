#!/usr/bin/env python3
"""Export Avatar Textzuordnung.csv from Numbers source + sync video/OSC catalogs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEDIA_VIDEO = REPO_ROOT / "media" / "video"
NUMBERS_DEFAULT = MEDIA_VIDEO / "Textzuordnung Del-Wolf-28-06-26 Final-2.numbers"
CSV_OUT = MEDIA_VIDEO / "Avatar Textzuordnung.csv"
OSC_AVATAR_OUT = MEDIA_VIDEO / "OSCBefehllisteAvatare.txt"
SCRIPT_TXT = REPO_ROOT / "Stücktext" / "AVATAR Text Delfin bis Wolf.txt"
VIDEO_CSV = MEDIA_VIDEO / "Video Übersicht.csv"
PROJECTOR_CSV = MEDIA_VIDEO / "Projektor Übersicht.csv"

NUMBERS_TO_PIXERA: dict[str, str] = {
    "Hier unter der Erde": "HierUnterDerErde",
    "Kuscheltier Schlachtung": "KuscheltierSchlachtung",
    "Der Hase verlässt die Bühne": "DerHaseVerlaesstDieBuehne",
    "Der Hase verlässt die Bühne": "DerHaseVerlaesstDieBuehne",
    "BK8_Hai Schaedel": "BK8_HaiSchaedel",
    "BK8_Mavie 1": "BK8_Mavie1",
    "LG1_Das Lamm Gottes": "DasLammGottes",
}

# Extra stems that resolve scene_ref / id → on-disk MP4 name (without extension).
MEDIA_FILE_ALIASES: dict[str, tuple[str, ...]] = {
    "daslammgottes": ("lg1daslammgottes", "lg1_das_lamm_gottes"),
    "mo3caro": ("mo3dachscaro", "mo3_dachs_caro"),
    "mo3_caro": ("mo3dachscaro", "mo3_dachs_caro"),
    "sch2azariawirdschaf": ("sch2azariawirdschaf",),
    "sch3ingewirdschaf": ("sch3ingewirdschaf",),
}

_VALID_AVATARS = frozenset({"delphin", "baerenklau", "lamm", "petya", "wolf"})


def slug_id(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    return normalized.strip("_")


def normalize_media_key(value: str) -> str:
    """NFKD + drop non-alnum for fuzzy MP4 stem matching."""
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def numbers_clip_to_pixera(name: str) -> str:
    stripped = name.strip()
    if stripped in NUMBERS_TO_PIXERA:
        return NUMBERS_TO_PIXERA[stripped]
    compact = stripped.replace(" ", "")
    decomposed = unicodedata.normalize("NFKD", compact)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def infer_avatar(clip_name: str) -> str:
    upper = clip_name.upper().replace(" ", "")
    if upper.startswith(("BK", "BAK", "BÄK", "BAEK")):
        return "baerenklau"
    if upper.startswith("LG") or upper.startswith("DASLAMM"):
        return "lamm"
    if upper.startswith("PET"):
        return "petya"
    if upper.startswith("WO"):
        return "wolf"
    if upper.startswith(("MO", "SCH", "DEL", "HIER", "KUSCHELTIER", "DERHASE")):
        return "delphin"
    return "delphin"


def parse_zeit_duration_ms(value: object) -> int | None:
    """Numbers «Zeit»: Sekunden (0:07:00 = 7 s) oder MM:SS (0:01:30 = 90 s)."""
    from app.services.avatar_duration import parse_zeit_duration_ms as _parse

    return _parse(value)


def _header_names(table) -> list[str]:
    return [
        str(table.cell(0, c).value or "").strip().lower()
        for c in range(table.num_cols)
    ]


def _is_catalog_header(headers: list[str]) -> bool:
    return "id" in headers and "text" in headers and (
        "scene_ref" in headers or "avatar" in headers
    )


def _cell_str(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "null"}:
        return ""
    return text


def _parse_duration_cell(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        ms = int(round(float(value)))
        return ms if ms > 0 else None
    text = _cell_str(value)
    if text.isdigit():
        ms = int(text)
        return ms if ms > 0 else None
    return parse_zeit_duration_ms(value)


def complete_row(row: dict[str, str | int]) -> dict[str, str | int]:
    """Fill missing avatar / video_clip_id from scene_ref or id."""
    cue_id = _cell_str(row.get("id"))
    scene_ref = _cell_str(row.get("scene_ref"))
    text = _cell_str(row.get("text"))
    if not cue_id and scene_ref:
        cue_id = slug_id(scene_ref)
    if not scene_ref and cue_id:
        scene_ref = numbers_clip_to_pixera(cue_id)

    avatar_raw = _cell_str(row.get("avatar")).lower()
    if avatar_raw not in _VALID_AVATARS:
        avatar_raw = infer_avatar(scene_ref or cue_id)

    clip_id = _cell_str(row.get("video_clip_id")).lower() or cue_id

    out: dict[str, str | int] = {
        "id": cue_id,
        "text": text,
        "avatar": avatar_raw,
        "video_clip_id": clip_id,
        "scene_ref": scene_ref,
    }
    duration = row.get("duration_ms")
    if isinstance(duration, int) and duration > 0:
        out["duration_ms"] = duration
    elif duration not in (None, ""):
        parsed = _parse_duration_cell(duration)
        if parsed is not None:
            out["duration_ms"] = parsed
    return out


def export_from_catalog_numbers(table) -> list[dict[str, str | int]]:
    """Numbers saved from Avatar Textzuordnung.csv (id/text/avatar/…)."""
    headers = _header_names(table)
    col = {name: idx for idx, name in enumerate(headers) if name}

    rows: list[dict[str, str | int]] = []
    for r in range(1, table.num_rows):
        def cell(name: str) -> object:
            idx = col.get(name)
            if idx is None:
                return None
            return table.cell(r, idx).value

        cue_id = _cell_str(cell("id"))
        text = _cell_str(cell("text"))
        if not cue_id and not text:
            continue
        if not text:
            continue
        scene_ref = _cell_str(cell("scene_ref"))
        row = complete_row(
            {
                "id": cue_id or slug_id(scene_ref),
                "text": text,
                "avatar": _cell_str(cell("avatar")),
                "video_clip_id": _cell_str(cell("video_clip_id")),
                "scene_ref": scene_ref,
                "duration_ms": _parse_duration_cell(cell("duration_ms")) or "",
            }
        )
        if row.get("id") and row.get("text") and row.get("scene_ref"):
            rows.append(row)
    return rows


def export_from_zeit_numbers(table) -> list[dict[str, str | int]]:
    """Classic Numbers: clip name | text | Zeit."""
    rows: list[dict[str, str | int]] = []
    for r in range(1, table.num_rows):
        clip_raw = table.cell(r, 0).value
        text = table.cell(r, 1).value
        zeit = table.cell(r, 2).value if table.num_cols > 2 else None
        if not clip_raw or not text:
            continue
        clip_name = str(clip_raw).strip()
        pixera = numbers_clip_to_pixera(clip_name)
        cue_id = slug_id(pixera)
        duration_ms = parse_zeit_duration_ms(zeit)
        row: dict[str, str | int] = {
            "id": cue_id,
            "text": str(text).strip(),
            "avatar": infer_avatar(clip_name),
            "video_clip_id": cue_id,
            "scene_ref": pixera,
        }
        if duration_ms is not None:
            row["duration_ms"] = duration_ms
        rows.append(row)
    return rows


def export_from_numbers(path: Path) -> list[dict[str, str | int]]:
    from numbers_parser import Document

    doc = Document(path)
    table = doc.sheets[0].tables[0]
    headers = _header_names(table)
    if _is_catalog_header(headers):
        return export_from_catalog_numbers(table)
    return export_from_zeit_numbers(table)


def index_media_folder(folder: Path) -> dict[str, Path]:
    """Map normalize_media_key(stem) → path for video files."""
    index: dict[str, Path] = {}
    if not folder.is_dir():
        return index
    for path in folder.iterdir():
        if path.suffix.lower() not in {".mp4", ".mov", ".m4v", ".mkv"}:
            continue
        key = normalize_media_key(path.stem)
        # Prefer shorter / canonical names when duplicates collide (first wins).
        index.setdefault(key, path)
    return index


def resolve_media_file(
    row: dict[str, str | int],
    media_index: dict[str, Path],
) -> Path | None:
    """Find MP4 for a cue via scene_ref / id / aliases."""
    candidates: list[str] = []
    for field in ("scene_ref", "id", "video_clip_id"):
        raw = _cell_str(row.get(field))
        if not raw:
            continue
        candidates.append(normalize_media_key(raw))
        for alias in MEDIA_FILE_ALIASES.get(normalize_media_key(raw), ()):
            candidates.append(normalize_media_key(alias))
        for alias in MEDIA_FILE_ALIASES.get(raw.lower(), ()):
            candidates.append(normalize_media_key(alias))

    for key in candidates:
        hit = media_index.get(key)
        if hit is not None:
            return hit
    return None


def probe_duration_ms(path: Path) -> int | None:
    """Prefer ffprobe; fall back to macOS mdls."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.check_output(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            seconds = float(out)
            if seconds > 0:
                return int(round(seconds * 1000))
        except (subprocess.CalledProcessError, ValueError, OSError):
            pass

    mdls = shutil.which("mdls")
    if mdls:
        try:
            out = subprocess.check_output(
                ["mdls", "-name", "kMDItemDurationSeconds", "-raw", str(path)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if out and out != "(null)":
                seconds = float(out)
                if seconds > 0:
                    return int(round(seconds * 1000))
        except (subprocess.CalledProcessError, ValueError, OSError):
            pass
    return None


def apply_media_durations(
    rows: list[dict[str, str | int]],
    media_folder: Path,
) -> tuple[int, list[str]]:
    """Overwrite duration_ms from media files. Returns (updated, missing_ids)."""
    media_index = index_media_folder(media_folder)
    updated = 0
    missing: list[str] = []
    for row in rows:
        path = resolve_media_file(row, media_index)
        if path is None:
            missing.append(str(row.get("id") or row.get("scene_ref") or "?"))
            continue
        duration = probe_duration_ms(path)
        if duration is None:
            missing.append(str(row.get("id") or "?"))
            continue
        row["duration_ms"] = duration
        updated += 1
    return updated, missing


def write_avatar_csv(rows: list[dict[str, str | int]]) -> None:
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "text", "avatar", "video_clip_id", "scene_ref", "duration_ms"],
            delimiter=";",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "avatar": row["avatar"],
                    "video_clip_id": row["video_clip_id"],
                    "scene_ref": row["scene_ref"],
                    "duration_ms": row.get("duration_ms", ""),
                }
            )


def write_script_txt(rows: list[dict[str, str | int]]) -> None:
    seen: set[str] = set()
    parts: list[str] = []
    for row in rows:
        key = " ".join(str(row["text"]).split())
        if key in seen:
            continue
        seen.add(key)
        parts.append(str(row["text"]))
    SCRIPT_TXT.parent.mkdir(parents=True, exist_ok=True)
    SCRIPT_TXT.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def load_projector_prefixes() -> list[str]:
    prefixes: list[str] = []
    if PROJECTOR_CSV.is_file():
        with PROJECTOR_CSV.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                prefix = (row.get("pixera_prefix") or "").strip()
                if prefix:
                    prefixes.append(prefix)
    if not prefixes:
        prefixes = ["KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"]
    return prefixes


def write_osc_avatar_befehlliste(rows: list[dict[str, str | int]]) -> int:
    """Write OSC cue/apply lines for every avatar clip on all projectors."""
    scene_refs = [str(row["scene_ref"]) for row in rows]
    prefixes = load_projector_prefixes()
    blocks: list[str] = []
    for prefix in prefixes:
        blocks.extend(
            f'("/pixera/args/cue/apply", "{prefix}.{scene_ref}")' for scene_ref in scene_refs
        )
        blocks.append("")
    OSC_AVATAR_OUT.parent.mkdir(parents=True, exist_ok=True)
    OSC_AVATAR_OUT.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    return len(scene_refs) * len(prefixes)


def parse_osc_clip_names() -> dict[str, str]:
    from app.director.media.video_inventory import parse_osc_befehlliste

    names: dict[str, str] = {}
    for filename in ("OSCBefehllisteOhneAvatare.txt", "OSCBefehllisteAvatare.txt"):
        path = MEDIA_VIDEO / filename
        if not path.is_file():
            continue
        for _prefix, pixera_name in parse_osc_befehlliste(path):
            names[slug_id(pixera_name)] = pixera_name
    return names


def sync_video_overview(rows: list[dict[str, str | int]], osc_clips: dict[str, str]) -> None:
    existing: dict[str, dict[str, str]] = {}
    if VIDEO_CSV.is_file():
        with VIDEO_CSV.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                clip_id = (row.get("clip_id") or "").strip()
                if clip_id:
                    existing[clip_id] = row

    for row in rows:
        clip_id = str(row["video_clip_id"])
        pixera_name = str(row["scene_ref"])
        existing[clip_id] = {
            "clip_id": clip_id,
            "pixera_name": pixera_name,
            "beschreibung": pixera_name,
            "tags": str(row.get("avatar", "")),
            "stimmungen": "neutral,spannung",
        }

    for clip_id, pixera_name in sorted(osc_clips.items()):
        if clip_id in existing:
            existing[clip_id]["pixera_name"] = pixera_name
            continue
        existing[clip_id] = {
            "clip_id": clip_id,
            "pixera_name": pixera_name,
            "beschreibung": pixera_name,
            "tags": clip_id,
            "stimmungen": "neutral,spannung",
        }

    fieldnames = ["clip_id", "pixera_name", "beschreibung", "tags", "stimmungen"]
    VIDEO_CSV.parent.mkdir(parents=True, exist_ok=True)
    with VIDEO_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for clip_id in sorted(existing.keys()):
            row = existing[clip_id]
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sync_video_cue_durations(rows: list[dict[str, str | int]]) -> int:
    """Write duration_ms + video_type avatar into data/video_cues.json."""
    from app.services.video_cue_catalog import catalog_json_path

    path = catalog_json_path()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"version": 1, "osc_address": "/pixera/args/cue/apply", "projectors": [], "clips": []}

    clips_by_id = {c["id"]: c for c in payload.get("clips", []) if c.get("id")}
    updated = 0
    for row in rows:
        clip_id = str(row.get("video_clip_id") or "").strip()
        duration = row.get("duration_ms")
        if not clip_id or not duration:
            continue
        clip = clips_by_id.get(
            clip_id,
            {
                "id": clip_id,
                "pixera_name": row.get("scene_ref", clip_id),
                "label": row.get("scene_ref", clip_id),
                "description": row.get("scene_ref", clip_id),
                "tags": [str(row.get("avatar", ""))],
                "moods": ["neutral", "spannung"],
                "intensity_min": 0.0,
                "intensity_max": 1.0,
                "projector_preference": None,
                "text_content_id": None,
                "animal": None,
            },
        )
        clip["pixera_name"] = str(row.get("scene_ref") or clip.get("pixera_name") or clip_id)
        clip["duration_ms"] = int(duration)
        clip["video_type"] = "avatar"
        clip["can_be_interrupted"] = False
        clips_by_id[clip_id] = clip
        updated += 1

    payload["clips"] = sorted(clips_by_id.values(), key=lambda c: c["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated


def refresh_avatar_speech_cache() -> int:
    """Write data/avatar_speech.json from the CSV we just exported (repo-root data/)."""
    from app.services.avatar_speech_catalog import parse_avatar_csv

    catalog = parse_avatar_csv(CSV_OUT)
    path = REPO_ROOT / "data" / "avatar_speech.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": catalog.version,
        "_source": str(CSV_OUT),
        "cues": [c.model_dump() for c in catalog.cues],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(catalog.cues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "numbers_path",
        nargs="?",
        type=Path,
        default=NUMBERS_DEFAULT,
        help="Path to Avatar Textzuordnung .numbers",
    )
    parser.add_argument(
        "--media-folder",
        type=Path,
        default=None,
        help="Folder with avatar MP4s; overwrites duration_ms from file lengths",
    )
    args = parser.parse_args(argv)

    numbers_path = args.numbers_path
    if not numbers_path.is_file():
        print(f"Numbers-Datei nicht gefunden: {numbers_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    rows = export_from_numbers(numbers_path)
    if not rows:
        print("Keine Avatar-Zeilen in Numbers gefunden.", file=sys.stderr)
        return 1

    media_updated = 0
    media_missing: list[str] = []
    if args.media_folder is not None:
        if not args.media_folder.is_dir():
            print(f"Media-Ordner nicht gefunden: {args.media_folder}", file=sys.stderr)
            return 1
        media_updated, media_missing = apply_media_durations(rows, args.media_folder)

    write_avatar_csv(rows)
    write_script_txt(rows)
    osc_line_count = write_osc_avatar_befehlliste(rows)
    osc_clips = parse_osc_clip_names()
    sync_video_overview(rows, osc_clips)
    duration_count = sync_video_cue_durations(rows)
    cache_count = refresh_avatar_speech_cache()

    print(f"Exported {len(rows)} avatar cues → {CSV_OUT.name}")
    print(f"Wrote {osc_line_count} OSC lines → {OSC_AVATAR_OUT.name}")
    print(f"Updated {VIDEO_CSV.name} ({len(rows)} avatar clips)")
    print(f"Updated {SCRIPT_TXT.name}")
    print(f"Set duration_ms on {duration_count} avatar clips in video_cues.json")
    print(f"Cached {cache_count} cues in avatar_speech.json")
    if args.media_folder is not None:
        print(f"Applied MP4 durations to {media_updated}/{len(rows)} cues from {args.media_folder}")
        if media_missing:
            print(f"Missing media/duration for: {', '.join(media_missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
