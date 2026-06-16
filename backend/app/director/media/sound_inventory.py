import csv
import re
from pathlib import Path

from app.schemas.sound_cues import SoundCueCatalog, SoundCueDefaults, SoundCueEntry

SOUND_ACTIONS = frozenset({"play", "fade_in", "fade_out"})


def resolve_sound_overview_path(data_dir: Path) -> Path | None:
    resolved_data = data_dir.resolve() if data_dir.is_absolute() else (Path.cwd() / data_dir).resolve()
    candidates = [
        resolved_data.parent / "media" / "sound" / "Sound Übersicht.csv",
        data_dir.parent / "media" / "sound" / "Sound Übersicht.csv",
        Path.cwd() / "media" / "sound" / "Sound Übersicht.csv",
        Path.cwd().parent / "media" / "sound" / "Sound Übersicht.csv",
        Path("/app") / "media" / "sound" / "Sound Übersicht.csv",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _slug_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    return normalized.strip("_")


def load_sound_cues_from_csv(path: Path) -> SoundCueCatalog:
    cues: list[SoundCueEntry] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            cue_id = _slug_id(row.get("cue_id", ""))
            if not cue_id:
                continue
            action = (row.get("aktion") or "play").strip().lower()
            if action not in SOUND_ACTIONS:
                raise ValueError(f"Unknown sound action {action!r} for cue {cue_id}")
            soundname = (row.get("soundname") or cue_id).strip()
            description = (row.get("beschreibung") or "").strip()
            midi_note = int(row.get("midi_note", "0"))
            channel_raw = row.get("kanal") or row.get("channel")
            channel = int(channel_raw) if channel_raw else None
            tags = _split_list(row.get("tags", ""))
            moods = _split_list(row.get("stimmungen") or row.get("moods", ""))
            if action != "play":
                tags = list(dict.fromkeys([*tags, action]))
            ableton_hint = f"{soundname} — {action} (Note {midi_note})"
            cues.append(
                SoundCueEntry(
                    id=cue_id,
                    label=soundname,
                    soundname=soundname,
                    action=action,
                    description=description,
                    ableton_hint=ableton_hint,
                    midi_note=midi_note,
                    channel=channel,
                    tags=tags or [soundname.lower().replace(" ", "_")],
                    moods=moods or ["neutral"],
                )
            )
    return SoundCueCatalog(
        defaults=SoundCueDefaults(),
        cues=cues,
    )
