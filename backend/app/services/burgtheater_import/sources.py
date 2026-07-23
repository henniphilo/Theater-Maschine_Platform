"""Read-only discovery of Burgtheater legacy sources (never mutates them)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CATALOG_FILES = (
    "video_cues.json",
    "sound_cues.json",
    "light_scenes.json",
    "light_inventory.json",
    "dramaturgy_rules.json",
    "avatar_speech.json",
    "sound_inventory.json",
    "sound_midi_map.json",
    "media.json",
)

MEDIA_SUBDIRS = ("video", "sound", "audio", "light", "recordings")

VIDEO_CSV_CANDIDATES = (
    "media/video/Video Übersicht.csv",
    "media/video/Video Uebersicht.csv",
    "media/video/Videozuordnung KI.csv",
)
SOUND_CSV_CANDIDATES = (
    "media/sound/Sound Übersicht.csv",
    "media/sound/Sound Uebersicht.csv",
)
PROJECTOR_CSV_CANDIDATES = (
    "media/video/Projektor Übersicht.csv",
    "media/video/Projektor Uebersicht.csv",
)

MEDIA_EXTENSIONS = {
    ".mov",
    ".mp4",
    ".m4v",
    ".avi",
    ".webm",
    ".mkv",
    ".wav",
    ".aiff",
    ".aif",
    ".mp3",
    ".m4a",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".txt",
    ".csv",
    ".json",
    ".md",
    ".xlsx",
}


@dataclass
class DiscoveredSources:
    repo_root: Path
    data_dir: Path
    media_dir: Path
    catalogs: dict[str, Path] = field(default_factory=dict)
    catalog_payloads: dict[str, Any] = field(default_factory=dict)
    media_files: list[Path] = field(default_factory=list)
    video_csv: Path | None = None
    sound_csv: Path | None = None
    projector_csv: Path | None = None
    missing_expected: list[str] = field(default_factory=list)


def resolve_repo_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    # services/burgtheater_import → services → app → backend → repo
    here = Path(__file__).resolve()
    return here.parents[4]


def discover_sources(
    *,
    repo_root: Path | None = None,
    data_dir: Path | None = None,
    media_dir: Path | None = None,
) -> DiscoveredSources:
    root = resolve_repo_root(repo_root)
    data = (data_dir or (root / "data")).resolve()
    media = (media_dir or (root / "media")).resolve()
    discovered = DiscoveredSources(repo_root=root, data_dir=data, media_dir=media)

    for name in CATALOG_FILES:
        path = data / name
        if path.is_file():
            discovered.catalogs[name] = path
            with path.open(encoding="utf-8") as handle:
                discovered.catalog_payloads[name] = json.load(handle)
        else:
            discovered.missing_expected.append(f"data/{name}")

    if media.is_dir():
        for sub in MEDIA_SUBDIRS:
            folder = media / sub
            if not folder.is_dir():
                continue
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.name.startswith("."):
                    continue
                if path.suffix.lower() in MEDIA_EXTENSIONS:
                    discovered.media_files.append(path)

    discovered.video_csv = _first_existing(root, VIDEO_CSV_CANDIDATES)
    discovered.sound_csv = _first_existing(root, SOUND_CSV_CANDIDATES)
    discovered.projector_csv = _first_existing(root, PROJECTOR_CSV_CANDIDATES)

    if discovered.video_csv is None:
        discovered.missing_expected.append(VIDEO_CSV_CANDIDATES[0])
    if discovered.sound_csv is None:
        discovered.missing_expected.append(SOUND_CSV_CANDIDATES[0])

    return discovered


def _first_existing(root: Path, candidates: tuple[str, ...]) -> Path | None:
    for rel in candidates:
        path = root / rel
        if path.is_file():
            return path.resolve()
    return None


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
