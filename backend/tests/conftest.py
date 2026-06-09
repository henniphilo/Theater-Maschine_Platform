from pathlib import Path

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def director_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    backend_or_app_root = Path(__file__).resolve().parents[1]
    repo_data = backend_or_app_root / "data"
    if not repo_data.exists():
        repo_data = Path(__file__).resolve().parents[2] / "data"
    monkeypatch.setattr(settings, "director_enabled", True)
    monkeypatch.setattr(settings, "osc_dry_run", True)
    monkeypatch.setattr(settings, "director_data_dir", str(repo_data))
    monkeypatch.setattr(settings, "director_log_path", str(tmp_path / "director.log"))
    monkeypatch.setattr(settings, "director_autopilot_default", True)

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

    pipeline_mod._pipeline = None
    director_routes._pipeline = pipeline_mod.get_director_pipeline()
    director_routes._recording = __import__(
        "app.director.recording", fromlist=["RecordingManager"]
    ).RecordingManager(
        touchdesigner=director_routes._pipeline.touchdesigner,
        media_db=director_routes._pipeline.media_db,
    )
