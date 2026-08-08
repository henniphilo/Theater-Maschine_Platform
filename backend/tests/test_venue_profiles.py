"""Venue profile switch + multi-host Pixera fan-out."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.director.output_targets import (
    apply_overrides,
    effective_video_target,
    effective_video_targets,
)
from app.director.outputs.pixera import PixeraBridge
from app.main import app
from app.services import venue_profiles as venue_mod

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "venue_profiles.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "active_id": "burgtheater",
                "profiles": [
                    {
                        "id": "burgtheater",
                        "label": "Burgtheater",
                        "self_host": None,
                        "video_hosts": ["172.27.27.1"],
                        "video_port": 8990,
                        "light_host": "10.101.90.112",
                        "light_port": 3032,
                        "notes": "test burg",
                    },
                    {
                        "id": "hallein",
                        "label": "Hallein",
                        "self_host": "192.168.14.15",
                        "video_hosts": ["192.168.14.11", "192.168.14.12"],
                        "video_port": 8990,
                        "light_host": None,
                        "light_port": None,
                        "notes": "test hallein",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    venue_mod.set_persist_path_override(path)
    apply_overrides(reset=True)
    yield
    venue_mod.set_persist_path_override(None)
    apply_overrides(reset=True)


def test_activate_hallein_sets_dual_video_hosts() -> None:
    res = client.post(
        "/api/v1/director/venue-profiles/activate",
        json={"profile_id": "hallein"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["active_id"] == "hallein"

    hosts = effective_video_targets()
    assert hosts == [("192.168.14.11", 8990), ("192.168.14.12", 8990)]
    assert effective_video_target() == ("192.168.14.11", 8990)

    targets = client.get("/api/v1/director/output-targets").json()
    assert [h["host"] for h in targets["video"]["effective_hosts"]] == [
        "192.168.14.11",
        "192.168.14.12",
    ]
    assert targets["venue_profile_id"] == "hallein"


def test_activate_burgtheater_restores_single_host() -> None:
    client.post("/api/v1/director/venue-profiles/activate", json={"profile_id": "hallein"})
    res = client.post(
        "/api/v1/director/venue-profiles/activate",
        json={"profile_id": "burgtheater"},
    )
    assert res.status_code == 200
    assert effective_video_targets() == [("172.27.27.1", 8990)]


def test_hallein_light_cleared_when_unknown() -> None:
    client.post("/api/v1/director/venue-profiles/activate", json={"profile_id": "burgtheater"})
    client.post("/api/v1/director/venue-profiles/activate", json={"profile_id": "hallein"})
    state = venue_mod.list_profiles()
    hallein = next(p for p in state.profiles if p.id == "hallein")
    assert hallein.light_configured is False


def test_pixera_bridge_fans_out_to_all_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, int, str, list]] = []

    class FakeClient:
        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port

        def send_message(self, address: str, args: list) -> None:
            sent.append((self.host, self.port, address, args))

    def fake_create(host: str, port: int) -> FakeClient:
        return FakeClient(host, port)

    monkeypatch.setattr("app.director.outputs.pixera.create_udp_client", fake_create)
    monkeypatch.setattr("app.director.outputs.pixera.settings.osc_dry_run", False)
    monkeypatch.setattr("app.director.outputs.pixera.log_osc_command", lambda *a, **k: None)

    bridge = PixeraBridge(
        hosts=[("192.168.14.11", 8990), ("192.168.14.12", 8990)],
        dry_run=False,
    )
    bridge.apply_cue("KI_Adam.Clyde")
    assert len(sent) == 2
    assert {row[0] for row in sent} == {"192.168.14.11", "192.168.14.12"}
    assert all(row[2] == "/pixera/args/cue/apply" for row in sent)
    assert all(row[3] == ["KI_Adam.Clyde"] for row in sent)


def test_patch_output_targets_accepts_comma_hosts() -> None:
    res = client.patch(
        "/api/v1/director/output-targets",
        json={"video_host": "10.0.0.1, 10.0.0.2", "video_port": 8990},
    )
    assert res.status_code == 200
    assert effective_video_targets() == [("10.0.0.1", 8990), ("10.0.0.2", 8990)]


def test_update_hallein_light_later() -> None:
    res = client.patch(
        "/api/v1/director/venue-profiles/hallein/light",
        json={"light_host": "192.168.14.20", "light_port": 3032},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["light_configured"] is True
    assert body["light_host"] == "192.168.14.20"
