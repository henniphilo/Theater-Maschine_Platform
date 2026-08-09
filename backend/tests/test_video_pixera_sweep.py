"""Tests for Technik-Test Pixera video cue sweep."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.director.video_pixera_sweep import (
    list_pixera_sweep_cues,
    reset_video_pixera_sweep_manager_for_tests,
)
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    reset_video_pixera_sweep_manager_for_tests()


def teardown_function() -> None:
    reset_video_pixera_sweep_manager_for_tests()


def test_list_pixera_sweep_cues_groups_by_clip_across_projectors() -> None:
    clips = list_pixera_sweep_cues("part2")
    assert len(clips) >= 4
    clip_names = [name for name, _ in clips]
    assert len(clip_names) == len(set(clip_names))
    clyde = next((prefixes for name, prefixes in clips if name == "Clyde"), None)
    assert clyde is not None
    assert clyde == ["KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"]


def test_video_sweep_sends_all_projectors_then_next_clip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "app.director.video_pixera_sweep.list_pixera_sweep_cues",
        lambda scope="part2": [
            ("Clyde", ["KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"]),
            ("Bonnie", ["KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"]),
        ],
    )
    monkeypatch.setattr(
        "app.director.video_pixera_sweep._report_path",
        lambda: tmp_path / "pixera_video_sweep_report.json",
    )

    applied: list[str] = []

    def _apply(cue_name: str) -> None:
        applied.append(cue_name)

    from app.api.routes import director as director_routes

    monkeypatch.setattr(director_routes._pipeline.pixera, "apply_cue", _apply)

    started = client.post(
        "/api/v1/director/technik/video-sweep/start",
        json={"scope": "part2", "gap_ms": 50},
    )
    assert started.status_code == 200
    body = started.json()
    assert body["active"] is True
    assert body["total"] == 2
    assert body["gap_ms"] == 50

    deadline = time.time() + 3.0
    status = body
    while time.time() < deadline:
        status = client.get("/api/v1/director/technik/video-sweep/status").json()
        if status["finished"]:
            break
        time.sleep(0.05)

    assert status["finished"] is True
    assert status["completed"] == 2
    assert status["failed_count"] == 0
    assert applied == [
        "KI_RZ21.Clyde",
        "KI_Adam.Clyde",
        "KI_Eva.Clyde",
        "KI_LED.Clyde",
        "KI_RZ21.Bonnie",
        "KI_Adam.Bonnie",
        "KI_Eva.Bonnie",
        "KI_LED.Bonnie",
    ]
    assert status["results"][0]["clip_name"] == "Clyde"
    assert status["report_path"]
    assert Path(status["report_path"]).is_file()


def test_video_sweep_records_projector_send_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "app.director.video_pixera_sweep.list_pixera_sweep_cues",
        lambda scope="part2": [
            ("Clyde", ["KI_Adam", "KI_Eva"]),
        ],
    )
    monkeypatch.setattr(
        "app.director.video_pixera_sweep._report_path",
        lambda: tmp_path / "pixera_video_sweep_report.json",
    )

    def _apply(cue_name: str) -> None:
        if "Eva" in cue_name:
            raise OSError("udp send failed")

    from app.api.routes import director as director_routes

    monkeypatch.setattr(director_routes._pipeline.pixera, "apply_cue", _apply)

    started = client.post(
        "/api/v1/director/technik/video-sweep/start",
        json={"gap_ms": 50},
    )
    assert started.status_code == 200

    deadline = time.time() + 3.0
    status = started.json()
    while time.time() < deadline:
        status = client.get("/api/v1/director/technik/video-sweep/status").json()
        if status["finished"]:
            break
        time.sleep(0.05)

    assert status["finished"] is True
    assert status["failed_count"] == 1
    assert status["failed"][0]["clip_name"] == "Clyde"
    assert "KI_Eva.Clyde" in (status["failed"][0]["error"] or "")
    assert "udp send failed" in (status["failed"][0]["error"] or "")


def test_video_sweep_default_gap_is_100ms(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "app.director.video_pixera_sweep.list_pixera_sweep_cues",
        lambda scope="part2": [("Clyde", ["KI_Adam"])],
    )
    monkeypatch.setattr(
        "app.director.video_pixera_sweep._report_path",
        lambda: tmp_path / "pixera_video_sweep_report.json",
    )
    from app.api.routes import director as director_routes

    monkeypatch.setattr(director_routes._pipeline.pixera, "apply_cue", MagicMock())

    started = client.post("/api/v1/director/technik/video-sweep/start", json={})
    assert started.status_code == 200
    assert started.json()["gap_ms"] == 100

    deadline = time.time() + 2.0
    while time.time() < deadline:
        status = client.get("/api/v1/director/technik/video-sweep/status").json()
        if status["finished"]:
            break
        time.sleep(0.05)
