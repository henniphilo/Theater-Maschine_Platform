from pathlib import Path

from app.director.media.database import MediaDatabase
from app.director.media.inventory import scan_visual_assets, resolve_media_root, VISUAL_EXTENSIONS


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
    repo_data = Path(__file__).resolve().parents[2] / "data"
    if not repo_data.exists():
        repo_data = Path(__file__).resolve().parents[1] / "data"
    media_root = resolve_media_root(repo_data)
    assets = scan_visual_assets(media_root)
    video_assets = [a for a in assets if a.type == "video"]
    scanned_paths = {Path(a.path).name for a in video_assets}
    on_disk = _video_files_on_disk(media_root)
    assert on_disk
    assert scanned_paths == on_disk


def test_media_database_loads_scanned_videos() -> None:
    db = MediaDatabase()
    assert len(db.videos) >= 3
    assert {v.id for v in db.videos} == {a.id for a in db.videos}
    assert db.sounds
    assert all(s.path.startswith("media/audio/dummy_") for s in db.sounds)


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
