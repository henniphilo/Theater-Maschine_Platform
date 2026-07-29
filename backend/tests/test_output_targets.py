from fastapi.testclient import TestClient

import pytest

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, VisualAction, VisualCue
from app.director.output_targets import (
    apply_overrides,
    default_light_target,
    default_video_target,
    effective_light_target,
    effective_video_target,
)
from app.director.outputs.light_tcp import get_light_tcp_session
from app.director.outputs.osc_commands import build_osc_commands
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_output_targets() -> None:
    apply_overrides(reset=True)


def test_default_video_target_uses_pixera_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "visual_output", "pixera")
    monkeypatch.setattr(settings, "pixera_osc_host", "10.0.0.1")
    monkeypatch.setattr(settings, "pixera_osc_port", 8990)
    host, port = default_video_target()
    assert host == "10.0.0.1"
    assert port == 8990


def test_effective_video_target_applies_override() -> None:
    apply_overrides(video_host="192.168.1.50", video_port=3004)
    host, port = effective_video_target()
    assert host == "192.168.1.50"
    assert port == 3004


def test_patch_output_targets_updates_effective_video() -> None:
    res = client.patch(
        "/api/v1/director/output-targets",
        json={"video_host": "127.0.0.1", "video_port": 3004},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["video"]["effective"]["host"] == "127.0.0.1"
    assert body["video"]["effective"]["port"] == 3004


def test_build_osc_commands_uses_video_override() -> None:
    apply_overrides(video_host="127.0.0.1", video_port=3004)
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
    )
    commands = build_osc_commands(decision, dry_run=True)
    pixera_cmds = [cmd for cmd in commands if cmd.bridge == "pixera"]
    assert pixera_cmds
    assert pixera_cmds[0].host == "127.0.0.1"
    assert pixera_cmds[0].port == 3004


def test_light_override_disconnects_tcp_session() -> None:
    session = get_light_tcp_session()
    session.open_session(dry_run=True)
    assert session.connected is True

    apply_overrides(light_host="10.0.0.2", light_port=4000)

    assert session.connected is False
    host, port = effective_light_target()
    assert host == "10.0.0.2"
    assert port == 4000


def test_reset_output_targets_restores_defaults() -> None:
    default_host, default_port = default_light_target()
    apply_overrides(light_host="10.0.0.9", light_port=9999)
    apply_overrides(reset=True)
    host, port = effective_light_target()
    assert host == default_host
    assert port == default_port


def test_get_output_targets_includes_defaults() -> None:
    res = client.get("/api/v1/director/output-targets")
    assert res.status_code == 200
    body = res.json()
    default_host, default_port = default_video_target()
    assert body["video"]["default"]["host"] == default_host
    assert body["video"]["default"]["port"] == default_port
