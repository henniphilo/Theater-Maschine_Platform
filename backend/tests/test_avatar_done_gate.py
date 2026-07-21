"""Tests for avatar done gate and wait API."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from app.core.config import settings
from app.director.avatar_done_gate import AvatarDoneGate, get_avatar_done_gate
from app.main import app


def test_gate_wait_completes_when_all_cues_signaled() -> None:
    gate = AvatarDoneGate()
    result_box: list[object] = []

    def _wait() -> None:
        result_box.append(gate.wait_for(["KI_RZ21.A", "KI_Adam.A"], timeout_ms=2000))

    thread = threading.Thread(target=_wait)
    thread.start()
    time.sleep(0.05)
    gate.signal_done("KI_RZ21.A")
    assert thread.is_alive()
    gate.signal_done("KI_Adam.A")
    thread.join(timeout=1.0)
    result = result_box[0]
    assert result.status == "done"
    assert result.received == ["KI_Adam.A", "KI_RZ21.A"]


def test_gate_wait_times_out_with_missing() -> None:
    gate = AvatarDoneGate()
    result = gate.wait_for(["KI_RZ21.Missing"], timeout_ms=50)
    assert result.status == "timeout"
    assert result.missing == ["KI_RZ21.Missing"]


def test_gate_accepts_early_orphan_done() -> None:
    gate = AvatarDoneGate()
    gate.signal_done("KI_RZ21.Early")
    result = gate.wait_for(["KI_RZ21.Early"], timeout_ms=500)
    assert result.status == "done"
    assert result.wait_ms == 0


def test_avatar_done_wait_api_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "avatar_done_gate_enabled", False)
    client = TestClient(app)
    response = client.post(
        "/api/v1/director/avatar-done/wait",
        json={"cue_names": ["KI_RZ21.A"], "timeout_ms": 100},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"


def test_avatar_done_wait_api_done(monkeypatch) -> None:
    monkeypatch.setattr(settings, "avatar_done_gate_enabled", True)
    get_avatar_done_gate().reset()
    client = TestClient(app)

    def _signal() -> None:
        time.sleep(0.05)
        get_avatar_done_gate().signal_done("KI_RZ21.A")

    threading.Thread(target=_signal, daemon=True).start()
    response = client.post(
        "/api/v1/director/avatar-done/wait",
        json={"cue_names": ["KI_RZ21.A"], "timeout_ms": 2000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["received"] == ["KI_RZ21.A"]


def test_director_status_includes_gate_flag(monkeypatch) -> None:
    monkeypatch.setattr(settings, "avatar_done_gate_enabled", True)
    client = TestClient(app)
    response = client.get("/api/v1/director/status")
    assert response.status_code == 200
    assert response.json()["avatar_done_gate_enabled"] is True
