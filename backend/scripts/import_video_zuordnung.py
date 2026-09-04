#!/usr/bin/env python3
"""Import atmosphere videos from Numbers → OSC ohne Avatare + video catalog."""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEDIA_VIDEO = REPO_ROOT / "media" / "video"
NUMBERS_DEFAULT = MEDIA_VIDEO / "Videozuordnung KI Del-Wolf-29-06-26 Final Kopie.numbers"
CSV_OUT = MEDIA_VIDEO / "Videozuordnung KI.csv"
OSC_ATMOSPHERE_OUT = MEDIA_VIDEO / "OSCBefehllisteOhneAvatare.txt"
VIDEO_CSV = MEDIA_VIDEO / "Video Übersicht.csv"
PROJECTOR_CSV = MEDIA_VIDEO / "Projektor Übersicht.csv"

EXCLUDED_ATMOSPHERE_PIXERA = frozenset({"Random", "Avatar2"})

NUMBERS_TO_PIXERA: dict[str, str] = {
    "Hier unter der Erde": "HierUnterDerErde",
    "Tier unter der Erde": "TierUnterDerErde",
    "Kuscheltier Schlachtung": "KuscheltierSchlachtung",
    "Der Hase verlässt die Bühne": "DerHaseVerlaesstDieBuehne",
    "Der Hase verlässt die Bühne": "DerHaseVerlaesstDieBuehne",
    "Affen Slow_Odysee 2001": "AffenSlowOdysee",
    "Kaefer im Museum laufen davon": "KaeferImMuseum",
    "Konzeption Unter Tieren Test": "KonzeptionUnterTieren",
    "Bitcoinfahrt": "Bitcoinfahrt",
    "Fisch und Wassergewächs": "FischUndWassergewäsch",
    "Sturm-Fischskelett": "SturmFischskellet",
    "Wasserfahrt": "Wasserfahrt",
    "Sebastian blurry und grün": "SebastianBlurry",
    "Mehlwürmer langsam": "MehlwuermerLangsam",
    "Mehlwürmner langsam": "MehlwuermerLangsam",
    "Esel läuft 27-05": "EselLaeuft",
    "Gehirn Test": "GehirnTest",
    "Peter Thiel als Pipita": "HundeThielAlsPipita",
    "Avatar_IV_Video-2": "Avatar_IV_Video2",
    "Avatar_IV_Video": "Avatar_IV_Video",
    "BK8_Hai Schaedel": "BK8_HaiSchaedel",
    "BK8_Mavie 1": "BK8_Mavie1",
    "LG1_Das Lamm Gottes": "DasLammGottes",
    # Chaos 15.08.2026 — Pixera-Cue-Namen mit Underscores (Screenshot / Numbers)
    "Bitcoin_and_worm": "Bitcoin_and_worm",
    "Brennender_Wald": "Brennender_Wald",
    "Flut": "Flut",
    "Massenproduktion": "Massenproduktion",
    "Schmetterlinge_laufen": "Schmetterlinge_laufen",
    # Exporte / Chaos 04.09.2026 Begleitvideos
    "Konzeptionsprobe_2 Test_030926": "Konzeptionsprobe_2_Test_030926",
    "Konzeptionsprobe_3 Test_030926": "Konzeptionsprobe_3_Test_030926",
    "Haut und Ameisen": "HautUndAmeisen",
    "Skorpione_rennen_nach_Geld": "Skorpione_rennen_nach_Geld",
}


def slug_id(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    return normalized.strip("_")


def numbers_clip_to_pixera(name: str) -> str:
    stripped = name.strip()
    if stripped in NUMBERS_TO_PIXERA:
        return NUMBERS_TO_PIXERA[stripped]
    # Already a Pixera-style id (no spaces/hyphens): keep underscores as-is.
    if re.fullmatch(r"[A-Za-z0-9_]+", stripped):
        return stripped
    compact = stripped.replace(" ", "").replace("-", "").replace("_", "")
    decomposed = unicodedata.normalize("NFKD", compact)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def parse_numbers_sheet_duration_ms(value: object) -> int | None:
    """Numbers «Zeit» on 2026-06-29 rows: H:MM as minutes+seconds (01:33 → 93 s)."""
    from app.services.avatar_duration import parse_zeit_duration_ms

    if not isinstance(value, datetime):
        return parse_zeit_duration_ms(value)
    if value.second == 0:
        total_sec = value.hour * 60 + value.minute
    else:
        total_sec = value.hour * 3600 + value.minute * 60 + value.second
    return total_sec * 1000 if total_sec > 0 else None


def _tags_from_description(description: str, clip_id: str) -> str:
    words = re.findall(r"[a-zäöüß]{4,}", description.lower())
    unique = list(dict.fromkeys(words))[:6]
    return ",".join(unique) if unique else clip_id


def export_from_numbers(path: Path) -> list[dict[str, str | int]]:
    from numbers_parser import Document

    doc = Document(path)
    table = doc.sheets[0].tables[0]
    rows: list[dict[str, str | int]] = []
    for r in range(1, table.num_rows):
        clip_raw = table.cell(r, 0).value
        description = table.cell(r, 1).value
        zeit = table.cell(r, 2).value if table.num_cols > 2 else None
        if not clip_raw:
            continue
        clip_name = str(clip_raw).strip()
        pixera = numbers_clip_to_pixera(clip_name)
        clip_id = slug_id(pixera)
        duration_ms = parse_numbers_sheet_duration_ms(zeit)
        desc = str(description).strip() if description else pixera
        row: dict[str, str | int] = {
            "clip_id": clip_id,
            "pixera_name": pixera,
            "clip_name": clip_name,
            "beschreibung": desc,
            "tags": _tags_from_description(desc, clip_id),
            "stimmungen": "neutral,spannung,atmosphaere",
        }
        if duration_ms is not None:
            row["duration_ms"] = duration_ms
        rows.append(row)
    return rows


def write_video_csv(rows: list[dict[str, str | int]]) -> None:
    fieldnames = ["clip_id", "pixera_name", "clip_name", "beschreibung", "tags", "stimmungen", "duration_ms"]
    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_projector_prefixes() -> list[str]:
    prefixes: list[str] = []
    if PROJECTOR_CSV.is_file():
        with PROJECTOR_CSV.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                prefix = (row.get("pixera_prefix") or "").strip()
                if prefix:
                    prefixes.append(prefix)
    return prefixes or ["KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"]


def parse_existing_osc_by_prefix(path: Path) -> dict[str, list[str]]:
    from app.director.media.video_inventory import parse_osc_befehlliste

    by_prefix: dict[str, list[str]] = {}
    if not path.is_file():
        return by_prefix
    for prefix, pixera_name in parse_osc_befehlliste(path):
        if pixera_name in EXCLUDED_ATMOSPHERE_PIXERA:
            continue
        by_prefix.setdefault(prefix, [])
        if pixera_name not in by_prefix[prefix]:
            by_prefix[prefix].append(pixera_name)
    return by_prefix


def merge_osc_atmosphere_befehlliste(rows: list[dict[str, str | int]]) -> tuple[int, int]:
    """Merge atmosphere clips into OSC list — only clips laid out on all projectors."""
    prefixes = load_projector_prefixes()
    by_prefix = parse_existing_osc_by_prefix(OSC_ATMOSPHERE_OUT)
    for prefix in prefixes:
        by_prefix.setdefault(prefix, [])

    new_clips = 0
    for row in rows:
        pixera_name = str(row["pixera_name"])
        if pixera_name in EXCLUDED_ATMOSPHERE_PIXERA:
            continue
        for prefix in prefixes:
            names = by_prefix[prefix]
            if pixera_name not in names:
                names.append(pixera_name)
                new_clips += 1

    common = None
    for prefix in prefixes:
        names = [name for name in by_prefix.get(prefix, []) if name not in EXCLUDED_ATMOSPHERE_PIXERA]
        common = set(names) if common is None else common & set(names)
    ordered = [name for name in by_prefix.get(prefixes[0], []) if name in (common or set())]

    blocks: list[str] = []
    for prefix in prefixes:
        for pixera_name in ordered:
            blocks.append(f'("/pixera/args/cue/apply", "{prefix}.{pixera_name}")')
        blocks.append("")

    OSC_ATMOSPHERE_OUT.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    return new_clips, len(prefixes) * len(ordered)


def sync_video_overview(rows: list[dict[str, str | int]]) -> None:
    existing: dict[str, dict[str, str]] = {}
    if VIDEO_CSV.is_file():
        with VIDEO_CSV.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                clip_id = (row.get("clip_id") or "").strip()
                if clip_id:
                    existing[clip_id] = row

    for row in rows:
        clip_id = str(row["clip_id"])
        existing[clip_id] = {
            "clip_id": clip_id,
            "pixera_name": str(row["pixera_name"]),
            "beschreibung": str(row["beschreibung"]),
            "tags": str(row["tags"]),
            "stimmungen": str(row.get("stimmungen", "neutral,spannung")),
        }

    fieldnames = ["clip_id", "pixera_name", "beschreibung", "tags", "stimmungen"]
    with VIDEO_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for clip_id in sorted(existing.keys()):
            row = existing[clip_id]
            writer.writerow({field: row.get(field, "") for field in fieldnames})


DEFAULT_PROJECTORS = [
    {
        "id": "rz21",
        "pixera_prefix": "KI_RZ21",
        "name": "RZ21",
        "description": "Großer Frontprojektor",
    },
    {
        "id": "adam",
        "pixera_prefix": "KI_Adam",
        "name": "Adam",
        "description": "Kleiner Bühnenbeamer",
    },
    {
        "id": "eva",
        "pixera_prefix": "KI_Eva",
        "name": "Eva",
        "description": "Kleiner Bühnenbeamer",
    },
    {
        "id": "led",
        "pixera_prefix": "KI_LED",
        "name": "LED",
        "description": "LED-Wand auf der Bühne",
    },
]


def ensure_projector_csv() -> None:
    """Write Projektor Übersicht.csv if missing (needed for video_cues projectors)."""
    if PROJECTOR_CSV.is_file():
        return
    PROJECTOR_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PROJECTOR_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["output_id", "pixera_prefix", "name", "beschreibung"],
            delimiter=";",
        )
        writer.writeheader()
        for projector in DEFAULT_PROJECTORS:
            writer.writerow(
                {
                    "output_id": projector["id"],
                    "pixera_prefix": projector["pixera_prefix"],
                    "name": projector["name"],
                    "beschreibung": projector["description"],
                }
            )


def sync_video_cues_json(rows: list[dict[str, str | int]]) -> int:
    """Merge atmosphere clips into repo-root data/video_cues.json."""
    path = REPO_ROOT / "data" / "video_cues.json"
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"version": 1, "osc_address": "/pixera/args/cue/apply", "projectors": [], "clips": []}

    if not payload.get("projectors"):
        payload["projectors"] = list(DEFAULT_PROJECTORS)

    clips_by_id = {c["id"]: c for c in payload.get("clips", []) if c.get("id")}
    updated = 0
    for row in rows:
        clip_id = str(row["clip_id"])
        clip = clips_by_id.get(
            clip_id,
            {
                "id": clip_id,
                "pixera_name": row["pixera_name"],
                "label": row["pixera_name"],
                "description": row["beschreibung"],
                "tags": str(row["tags"]).split(","),
                "moods": ["neutral", "spannung"],
                "intensity_min": 0.0,
                "intensity_max": 1.0,
                "video_type": "atmosphere",
                "projector_preference": None,
                "duration_ms": None,
                "text_content_id": None,
                "animal": None,
                "can_be_interrupted": True,
            },
        )
        clip["pixera_name"] = str(row["pixera_name"])
        clip["label"] = str(row["pixera_name"])
        clip["description"] = str(row["beschreibung"])
        clip["tags"] = [t.strip() for t in str(row["tags"]).split(",") if t.strip()]
        clip["video_type"] = "atmosphere"
        clip["can_be_interrupted"] = True
        duration = row.get("duration_ms")
        if duration:
            clip["duration_ms"] = int(duration)
        clips_by_id[clip_id] = clip
        updated += 1

    payload["clips"] = sorted(clips_by_id.values(), key=lambda c: c["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated


def main() -> int:
    numbers_path = Path(sys.argv[1]) if len(sys.argv) > 1 else NUMBERS_DEFAULT
    if not numbers_path.is_file():
        print(f"Numbers-Datei nicht gefunden: {numbers_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    rows = export_from_numbers(numbers_path)
    if not rows:
        print("Keine Videoclips in Numbers-Tabelle gefunden.", file=sys.stderr)
        return 1

    ensure_projector_csv()
    write_video_csv(rows)
    new_osc, total_osc = merge_osc_atmosphere_befehlliste(rows)
    sync_video_overview(rows)
    json_count = sync_video_cues_json(rows)

    print(f"Exported {len(rows)} atmosphere clips → {CSV_OUT.name}")
    print(f"OSC ohne Avatare: +{new_osc} neue Zeilen ({total_osc} gesamt) → {OSC_ATMOSPHERE_OUT.name}")
    print(f"Updated {VIDEO_CSV.name}")
    print(f"Updated {json_count} atmosphere clips in video_cues.json (video_type=atmosphere)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
