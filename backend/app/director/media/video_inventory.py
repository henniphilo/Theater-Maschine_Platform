import csv
import re
from pathlib import Path

from app.schemas.video_cues import VideoClipEntry, VideoCueCatalog, VideoProjectorEntry


def resolve_video_overview_paths(data_dir: Path) -> tuple[Path | None, Path | None]:
    roots = [
        data_dir.parent,
        Path.cwd(),
        Path("/app"),
    ]
    clips_path: Path | None = None
    projectors_path: Path | None = None
    for root in roots:
        candidate_clips = root / "media" / "video" / "Video Übersicht.csv"
        candidate_projectors = root / "media" / "video" / "Projektor Übersicht.csv"
        if candidate_clips.is_file():
            clips_path = candidate_clips.resolve()
        if candidate_projectors.is_file():
            projectors_path = candidate_projectors.resolve()
        if clips_path and projectors_path:
            break
    return clips_path, projectors_path


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _slug_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    return normalized.strip("_")


def load_video_cues_from_csv(
    clips_path: Path,
    projectors_path: Path | None = None,
) -> VideoCueCatalog:
    projectors: list[VideoProjectorEntry] = []
    if projectors_path and projectors_path.is_file():
        with projectors_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                output_id = _slug_id(row.get("output_id", ""))
                prefix = (row.get("pixera_prefix") or "").strip()
                if not output_id or not prefix:
                    continue
                projectors.append(
                    VideoProjectorEntry(
                        id=output_id,
                        pixera_prefix=prefix,
                        name=(row.get("name") or output_id).strip(),
                        description=(row.get("beschreibung") or "").strip(),
                    )
                )

    clips: list[VideoClipEntry] = []
    with clips_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            clip_id = _slug_id(row.get("clip_id", ""))
            pixera_name = (row.get("pixera_name") or "").strip()
            if not clip_id or not pixera_name:
                continue
            label = (row.get("label") or pixera_name).strip()
            clips.append(
                VideoClipEntry(
                    id=clip_id,
                    pixera_name=pixera_name,
                    label=label,
                    description=(row.get("beschreibung") or "").strip(),
                    tags=_split_list(row.get("tags", "")) or [clip_id],
                    moods=_split_list(row.get("stimmungen") or row.get("moods", "")) or ["neutral"],
                )
            )

    return VideoCueCatalog(projectors=projectors, clips=clips)
