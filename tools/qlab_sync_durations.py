#!/usr/bin/env python3
"""Sync video cue durations from open QLab workspace into catalogs (ms precision).

Updates:
  - media/video/Avatar Textzuordnung.csv  (source for avatar timing)
  - data/avatar_speech.json               (cache via catalog reload)
  - data/video_cues.json                  (clip.duration_ms)

Requires QLab 5 with an open workspace (AppleScript).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AVATAR_CSV = REPO_ROOT / "media" / "video" / "Avatar Textzuordnung.csv"
AVATAR_JSON = REPO_ROOT / "data" / "avatar_speech.json"
VIDEO_CUES_JSON = REPO_ROOT / "data" / "video_cues.json"
QLAB_CUE_LIST = REPO_ROOT / "data" / "qlab_cue_list_all.csv"

_PROJECTOR_PREFIX = re.compile(r"^KI_(?:RZ21|Adam|Eva|LED)\.", re.IGNORECASE)


def _normalize_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def parse_qlab_duration_seconds(raw: str) -> float | None:
    """Parse AppleScript duration (locale may use comma decimal)."""
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def seconds_to_ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def clip_part_from_cue_number(cue_number: str) -> str:
    if "." in cue_number:
        return cue_number.split(".", 1)[1]
    return cue_number


def projector_rank(cue_number: str) -> int:
    """Prefer RZ21 when projectors disagree."""
    upper = cue_number.upper()
    if upper.startswith("KI_RZ21."):
        return 0
    if upper.startswith("KI_ADAM."):
        return 1
    if upper.startswith("KI_EVA."):
        return 2
    if upper.startswith("KI_LED."):
        return 3
    return 9


def fetch_qlab_video_durations() -> list[tuple[str, str, float]]:
    """Return [(cue_number, cue_name, duration_seconds), ...] from front workspace."""
    script = '''tell application id "com.figure53.QLab.5"
    if (count of workspaces) is 0 then error "Kein QLab-Workspace geöffnet"
    tell front workspace
        set out to ""
        repeat with c in cues
            if q type of c is "Video" then
                set cueNum to q number of c
                set cueName to q name of c
                set dur to duration of c
                set out to out & cueNum & tab & cueName & tab & dur & linefeed
            end if
        end repeat
        return out
    end tell
end tell'''
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[tuple[str, str, float]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        cue_number, cue_name, dur_raw = parts[0].strip(), parts[1].strip(), parts[2]
        seconds = parse_qlab_duration_seconds(dur_raw)
        if seconds is None:
            continue
        rows.append((cue_number, cue_name, seconds))
    return rows


def load_qlab_alias_map(csv_path: Path) -> dict[str, set[str]]:
    """Map normalized name variants → clip_ids from export CSV."""
    aliases: dict[str, set[str]] = defaultdict(set)
    if not csv_path.is_file():
        return aliases
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            clip_id = (row.get("clip_id") or "").strip()
            if not clip_id:
                continue
            for field in (
                "clip_id",
                "clip_part",
                "pixera_catalog_name",
                "osc_list_name",
                "qlab_cue_number",
                "suggested_filename",
            ):
                raw = (row.get(field) or "").strip()
                if not raw:
                    continue
                if field == "qlab_cue_number":
                    raw = clip_part_from_cue_number(raw)
                if field == "suggested_filename" and "." in raw:
                    raw = Path(raw).stem
                aliases[_normalize_key(raw)].add(clip_id)
            # Also map cue-number suffix without projector for alias numbers
            cue_num = (row.get("qlab_cue_number") or "").strip()
            if cue_num:
                aliases[_normalize_key(clip_part_from_cue_number(cue_num))].add(clip_id)
    return aliases


def build_duration_by_clip_id(
    qlab_rows: list[tuple[str, str, float]],
    alias_map: dict[str, set[str]],
) -> tuple[dict[str, int], list[str]]:
    """Resolve QLab rows to clip_id → duration_ms; prefer RZ21 on conflict."""
    candidates: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    unmatched: list[str] = []

    for cue_number, cue_name, seconds in qlab_rows:
        duration_ms = seconds_to_ms(seconds)
        clip_part = clip_part_from_cue_number(cue_number)
        keys = {_normalize_key(clip_part), _normalize_key(cue_name)}
        clip_ids: set[str] = set()
        for key in keys:
            clip_ids |= alias_map.get(key, set())
        if not clip_ids:
            unmatched.append(f"{cue_number}\t{cue_name}\t{seconds}")
            continue
        rank = projector_rank(cue_number)
        for clip_id in clip_ids:
            candidates[clip_id].append((rank, duration_ms, cue_number))

    resolved: dict[str, int] = {}
    conflicts: list[str] = []
    for clip_id, entries in sorted(candidates.items()):
        entries_sorted = sorted(entries, key=lambda item: item[0])
        best_rank, best_ms, best_cue = entries_sorted[0]
        same_rank = [ms for rank, ms, _ in entries_sorted if rank == best_rank]
        if len(set(same_rank)) > 1:
            conflicts.append(f"{clip_id}: conflicting ms at preferred projector {same_rank}")
        other = {ms for _, ms, _ in entries_sorted}
        if len(other) > 1:
            conflicts.append(
                f"{clip_id}: projectors disagree {sorted(other)} — using {best_cue}={best_ms}ms"
            )
        resolved[clip_id] = best_ms
    return resolved, unmatched + conflicts


def duration_lookup(durations: dict[str, int], *names: str) -> int | None:
    """Find duration by clip_id or any alias name (normalized)."""
    by_norm = {_normalize_key(key): value for key, value in durations.items()}
    for name in names:
        raw = (name or "").strip()
        if not raw:
            continue
        if raw in durations:
            return durations[raw]
        norm = _normalize_key(raw)
        if norm in by_norm:
            return by_norm[norm]
        if norm in durations:
            return durations[norm]
    return None


def enrich_alias_map_from_catalogs(
    alias_map: dict[str, set[str]],
    *,
    avatar_csv: Path,
    video_cues: Path,
) -> None:
    if avatar_csv.is_file():
        with avatar_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                clip_id = (row.get("video_clip_id") or row.get("id") or "").strip()
                if not clip_id:
                    continue
                alias_map[_normalize_key(clip_id)].add(clip_id)
                scene = (row.get("scene_ref") or "").strip()
                if scene:
                    alias_map[_normalize_key(scene)].add(clip_id)
    if video_cues.is_file():
        payload = json.loads(video_cues.read_text(encoding="utf-8"))
        for clip in payload.get("clips", []):
            clip_id = (clip.get("id") or "").strip()
            if not clip_id:
                continue
            alias_map[_normalize_key(clip_id)].add(clip_id)
            pixera = (clip.get("pixera_name") or "").strip()
            if pixera:
                alias_map[_normalize_key(pixera)].add(clip_id)
            label = (clip.get("label") or "").strip()
            if label:
                alias_map[_normalize_key(label)].add(clip_id)


def update_avatar_csv(path: Path, durations: dict[str, int], *, dry_run: bool) -> tuple[int, int]:
    if not path.is_file():
        return 0, 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if "duration_ms" not in fieldnames:
        fieldnames.append("duration_ms")

    updated = 0
    missing = 0
    for row in rows:
        clip_id = (row.get("video_clip_id") or row.get("id") or "").strip()
        scene = (row.get("scene_ref") or "").strip()
        duration = duration_lookup(durations, clip_id, scene, row.get("id") or "")
        if duration is None:
            missing += 1
            continue
        old = (row.get("duration_ms") or "").strip()
        new = str(duration)
        if old != new:
            updated += 1
        row["duration_ms"] = new

    if not dry_run:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return updated, missing


def update_video_cues(path: Path, durations: dict[str, int], *, dry_run: bool) -> tuple[int, int]:
    if not path.is_file():
        return 0, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    clips = payload.get("clips", [])
    updated = 0
    missing = 0
    for clip in clips:
        clip_id = (clip.get("id") or "").strip()
        pixera = (clip.get("pixera_name") or "").strip()
        label = (clip.get("label") or "").strip()
        duration = duration_lookup(durations, clip_id, pixera, label)
        if duration is None:
            missing += 1
            continue
        if clip.get("duration_ms") != duration:
            updated += 1
        clip["duration_ms"] = duration
    if not dry_run:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated, missing


def update_avatar_speech_json(path: Path, durations: dict[str, int], *, dry_run: bool) -> tuple[int, int]:
    """Update repo-root data/avatar_speech.json durations in place."""
    if not path.is_file():
        return 0, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    cues = payload.get("cues", [])
    updated = 0
    missing = 0
    for cue in cues:
        clip_id = (cue.get("video_clip_id") or cue.get("id") or "").strip()
        scene = (cue.get("scene_ref") or "").strip()
        duration = duration_lookup(durations, clip_id, scene, cue.get("id") or "")
        if duration is None:
            missing += 1
            continue
        if cue.get("duration_ms") != duration:
            updated += 1
        cue["duration_ms"] = duration
    if not dry_run:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated, missing


def sync_durations(*, dry_run: bool = False, skip_cache: bool = False) -> int:
    print("Lese Video-Cues aus QLab…")
    qlab_rows = fetch_qlab_video_durations()
    print(f"  {len(qlab_rows)} Video-Cues")

    alias_map = load_qlab_alias_map(QLAB_CUE_LIST)
    enrich_alias_map_from_catalogs(alias_map, avatar_csv=AVATAR_CSV, video_cues=VIDEO_CUES_JSON)
    durations, notes = build_duration_by_clip_id(qlab_rows, alias_map)
    print(f"  {len(durations)} eindeutige Clips mit Dauer")

    for note in notes[:20]:
        print(f"  Hinweis: {note}")
    if len(notes) > 20:
        print(f"  … {len(notes) - 20} weitere Hinweise")

    avatar_updated, avatar_missing = update_avatar_csv(AVATAR_CSV, durations, dry_run=dry_run)
    json_updated, json_missing = (0, 0)
    if not skip_cache:
        json_updated, json_missing = update_avatar_speech_json(AVATAR_JSON, durations, dry_run=dry_run)
    video_updated, video_missing = update_video_cues(VIDEO_CUES_JSON, durations, dry_run=dry_run)

    mode = "Dry-run — würde ändern" if dry_run else "Aktualisiert"
    print(f"{mode}: Avatar-CSV {avatar_updated} Zeilen (ohne QLab-Match: {avatar_missing})")
    if not skip_cache:
        print(f"{mode}: avatar_speech.json {json_updated} Cues (ohne QLab-Match: {json_missing})")
    print(f"{mode}: video_cues.json {video_updated} Clips (ohne QLab-Match: {video_missing})")

    # Spot-check a few known clips
    samples = ("bak1_nicolaspflanzen3", "del2", "sch2_azaria", "affenslowodysee")
    for sample in samples:
        ms = duration_lookup(durations, sample)
        if ms is not None:
            print(f"  sample {sample}: {ms} ms ({ms / 1000:.3f} s)")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QLab Video-Dauern → Kataloge (ms)")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")
    parser.add_argument("--skip-cache", action="store_true", help="avatar_speech.json nicht neu schreiben")
    args = parser.parse_args(argv)
    try:
        return sync_durations(dry_run=args.dry_run, skip_cache=args.skip_cache)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or str(exc)).strip()
        print(f"Fehler: {err}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
