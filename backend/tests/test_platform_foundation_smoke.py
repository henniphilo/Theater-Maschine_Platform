"""Platform Foundation smoke tests — current runtime must stay reproducibly testable.

Covers only existing endpoints/catalogues; no new platform features.
OSC_DRY_RUN is forced true via conftest / run-tests.sh.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_smoke_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_smoke_director_status() -> None:
    response = client.get("/api/v1/director/status")
    assert response.status_code == 200
    body = response.json()
    assert "safety" in body
    assert isinstance(body["safety"], dict)
    for key in ("autopilot_enabled", "visuals_enabled", "sound_enabled", "lights_enabled"):
        assert key in body["safety"]
    assert "active_cues" in body
    assert "run_epoch" in body
    assert body["safety"].get("emergency_stop_active") is False


def test_smoke_media_configuration_loads() -> None:
    response = client.get("/api/v1/media/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["videos"], "video catalogue must not be empty"
    assert body["projectors"], "projector list must not be empty"
    assert body["sounds"], "sound catalogue must not be empty"
    assert body["lights"], "light scenes must not be empty"
    assert body["pixera"]["address"]
    assert body["data_dir"]
    assert settings.osc_dry_run is True
    assert body["touchdesigner"]["osc_dry_run"] is True
    assert body["pixera"]["osc_dry_run"] is True


def test_smoke_cue_dry_run_execute() -> None:
    """Fire a visual cue via osc-test; must execute under dry-run without live send."""
    assert settings.osc_dry_run is True

    catalog = client.get("/api/v1/media/catalog").json()
    clip_id = catalog["videos"][0]["id"]

    response = client.post(
        "/api/v1/director/osc-test",
        json={
            "send_visual": True,
            "send_sound": False,
            "send_light": False,
            "clip_id": clip_id,
            "stagger": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["executed"] is True
    assert body["blocked_reason"] is None
    assert body["dry_run"] is True
    assert body["messages"], "dry-run must still produce planned OSC messages"
    assert all(cmd.get("dry_run") is True for cmd in body["messages"])
