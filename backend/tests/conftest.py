import os

# Before app imports: avoid UDP socket setup during test collection (local .env may use host.docker.internal).
os.environ.setdefault("OSC_DRY_RUN", "true")
os.environ.setdefault("OSC_HOST", "127.0.0.1")

from pathlib import Path

import pytest

from app.core.config import settings

FIXTURE_MEDIA_VIDEO = Path(__file__).resolve().parent / "fixtures" / "media" / "video"


def _fixture_osc_path(data_dir: Path, *, filename: str | None = None) -> Path | None:
    from app.director.media.video_inventory import OSC_LEGACY_FILENAME

    target = filename or OSC_LEGACY_FILENAME
    candidate = FIXTURE_MEDIA_VIDEO / target
    return candidate if candidate.is_file() else None


@pytest.fixture(autouse=True)
def director_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    backend_or_app_root = Path(__file__).resolve().parents[1]
    repo_root_data = Path(__file__).resolve().parents[2] / "data"
    backend_data = backend_or_app_root / "data"
    repo_data = backend_data
    if not (backend_data / "light_scenes.json").exists() and (repo_root_data / "light_scenes.json").exists():
        repo_data = repo_root_data
    elif not repo_data.exists():
        repo_data = repo_root_data
    monkeypatch.setattr(settings, "director_enabled", True)
    monkeypatch.setattr(settings, "osc_dry_run", True)
    monkeypatch.setattr(settings, "osc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "director_data_dir", str(repo_data))
    monkeypatch.setattr(settings, "director_log_path", str(tmp_path / "director.log"))
    monkeypatch.setattr(settings, "director_autopilot_default", True)
    monkeypatch.setattr(settings, "director_execute_mode", "sequenced")
    monkeypatch.setattr(settings, "director_dramaturgy_mode", "rules")
    monkeypatch.setattr(settings, "director_osc_queue", False)

    import app.director.media.video_inventory as video_inventory_mod

    monkeypatch.setattr(
        video_inventory_mod,
        "resolve_osc_befehlliste_path",
        lambda data_dir, *, filename=None: _fixture_osc_path(data_dir, filename=filename),
    )

    from app.services.video_cue_catalog import get_video_cue_catalog_service

    from app.director.outputs.light_scene_tracker import reset_light_scene_tracker

    reset_light_scene_tracker()
    get_video_cue_catalog_service().clear_cache()

    import app.director.outputs.osc_queue as osc_queue_mod
    import app.director.pipeline as pipeline_mod
    import app.api.routes.director as director_routes
    from app.director.cues.safety import get_safety_state

    safety = get_safety_state()
    safety.autopilot_enabled = True
    safety.visuals_enabled = True
    safety.sound_enabled = True
    safety.lights_enabled = True
    safety.blackout_locked = True
    safety.emergency_stop_active = False

    osc_queue_mod._queue = None
    pipeline_mod._pipeline = None
    director_routes._pipeline = pipeline_mod.get_director_pipeline()
    director_routes._recording = __import__(
        "app.director.recording", fromlist=["RecordingManager"]
    ).RecordingManager(
        touchdesigner=director_routes._pipeline.touchdesigner,
        media_db=director_routes._pipeline.media_db,
    )

    import app.director.light_desk_test as light_desk_mod
    import app.director.technik_hold as technik_hold_mod
    from app.director.outputs.light_tcp import close_light_tcp

    technik_hold_mod._manager = None
    technik_hold_mod.get_technik_hold_manager(director_routes._pipeline).stop()
    light_desk_mod._manager = None
    try:
        light_desk_mod.get_light_desk_test_manager(director_routes._pipeline).disconnect()
    except Exception:
        close_light_tcp()
