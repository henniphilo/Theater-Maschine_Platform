from pathlib import Path

import pytest

from app.director.media.database import MediaDatabase
from app.director.media.inventory import scan_visual_assets, resolve_media_root, VISUAL_EXTENSIONS
from app.director.media.video_inventory import load_video_cues_from_csv, resolve_video_overview_paths
try:
    from tests.repo_paths import repo_data_dir
except ModuleNotFoundError:
    from repo_paths import repo_data_dir


def _video_files_on_disk(media_root: Path) -> set[str]:
    video_dir = media_root / "video"
    if not video_dir.is_dir():
        return set()
    return {
        p.name
        for p in video_dir.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in VISUAL_EXTENSIONS
    }


def test_scan_finds_all_video_files() -> None:
    repo_data = repo_data_dir()
    media_root = resolve_media_root(repo_data)
    on_disk = _video_files_on_disk(media_root)
    if not on_disk:
        pytest.skip("Keine Video-Dateien im Checkout (nur lokal mit media/video/*.mov|mp4)")

    assets = scan_visual_assets(media_root)
    video_assets = [a for a in assets if a.type == "video"]
    scanned_paths = {Path(a.path).name for a in video_assets}
    assert scanned_paths == on_disk


def test_video_overview_csv_loads() -> None:
    clips_path, projectors_path = resolve_video_overview_paths(repo_data_dir())
    if clips_path is None:
        pytest.skip("Video Übersicht.csv nicht im Checkout")

    catalog = load_video_cues_from_csv(clips_path, projectors_path)
    assert any(clip.id == "clyde" for clip in catalog.clips)
    assert any(projector.id == "rz21" for projector in catalog.projectors)


def test_media_database_loads_pixera_videos() -> None:
    db = MediaDatabase()
    assert len(db.videos) >= 3
    assert any(v.id == "clyde" for v in db.videos)
    assert all(v.path.startswith("pixera:") for v in db.videos)
    assert db.sounds
    assert any(s.id == "maschinen_grundader" for s in db.sounds)


def test_light_scenes_reference_channel_inventory() -> None:
    db = MediaDatabase()
    scene = next(s for s in db.light_scenes if s.id == "vorbuehnenzug")
    assert scene.channels == ["11-19"]
    assert "JB P12" in scene.fixtures
    pano = next(s for s in db.light_scenes if s.id == "panolatte_rechts")
    assert pano.channels == ["92", "94", "96", "98"]
    ol4 = next(s for s in db.light_scenes if s.id == "ol_4er_hmi")
    assert ol4.channels == ["6", "741", "742"]
    assert db.light_inventory.get("venue") == "Unter Tieren"
