import re
import unicodedata
from pathlib import Path

from app.director.media.database import SoundAsset, VideoAsset

VISUAL_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".webm", ".mkv"}
AUDIO_EXTENSIONS = {".wav", ".aiff", ".aif", ".mp3", ".m4a"}


def resolve_media_root(data_dir: Path) -> Path:
    candidates = [
        data_dir.parent / "media",
        data_dir / "media",
        Path.cwd() / "media",
        Path.cwd().parent / "media",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return (data_dir.parent / "media").resolve()


def resolve_repo_root(data_dir: Path) -> Path:
    media_root = resolve_media_root(data_dir)
    if media_root.name == "media":
        return media_root.parent
    return data_dir.parent


_UMLAUT_MAP = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"}
)


def _slug_id(stem: str) -> str:
    # macOS filenames often use NFD (base + combining marks); normalize for stable OSC ids.
    normalized = unicodedata.normalize("NFD", stem.strip())
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.translate(_UMLAUT_MAP).lower()
    normalized = re.sub(r"[^a-z0-9\-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def scan_visual_assets(media_root: Path) -> list[VideoAsset]:
    assets: list[VideoAsset] = []
    for folder, asset_type in (("video", "video"), ("recordings", "recording")):
        directory = media_root / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in VISUAL_EXTENSIONS:
                continue
            asset_id = _slug_id(path.stem)
            tags = [asset_id, folder]
            if asset_type == "recording":
                tags.extend(["live", "recording"])
            assets.append(
                VideoAsset(
                    id=asset_id,
                    type=asset_type,
                    path=f"media/{folder}/{path.name}",
                    tags=tags,
                    moods=["neutral"],
                    intensity_min=0.0,
                    intensity_max=1.0,
                    duration=0.0,
                    loopable=asset_type == "video",
                    preferred_blend="slow_fade",
                )
            )
    return assets


def load_sound_assets(media_root: Path, repo_root: Path, media_json_sounds: list[dict]) -> list[SoundAsset]:
    sounds: list[SoundAsset] = []
    for entry in media_json_sounds:
        asset = SoundAsset.model_validate(entry)
        file_path = repo_root / asset.path
        if file_path.is_file():
            sounds.append(asset)

    audio_dir = media_root / "audio"
    if audio_dir.is_dir():
        known_paths = {s.path for s in sounds}
        for path in sorted(audio_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            rel = f"media/audio/{path.name}"
            if rel in known_paths:
                continue
            asset_id = _slug_id(path.stem)
            sounds.append(
                SoundAsset(
                    id=asset_id,
                    type="sound",
                    path=rel,
                    tags=[asset_id, "audio", "dummy"],
                    moods=["neutral"],
                    intensity_min=0.0,
                    intensity_max=1.0,
                )
            )
    return sounds


def partition_visual_assets(assets: list[VideoAsset]) -> tuple[list[VideoAsset], list[VideoAsset]]:
    clips = [a for a in assets if a.type == "video"]
    recordings = [a for a in assets if a.type == "recording"]
    return clips, recordings
