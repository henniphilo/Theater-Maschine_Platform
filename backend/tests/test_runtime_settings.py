"""Tests for operator runtime settings overlays."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.director.runtime_settings import (
    apply_runtime_settings,
    get_snapshot,
    reset_runtime_settings_for_tests,
)
from app.main import app

client = TestClient(app)


def test_apply_dramaturgy_mode_override(tmp_path: Path) -> None:
    reset_runtime_settings_for_tests(persist_path=tmp_path / "runtime_settings.json")
    apply_runtime_settings({"director_dramaturgy_mode": "llm"})
    assert settings.director_dramaturgy_mode == "llm"
    snap = get_snapshot()
    assert snap["overrides"]["director_dramaturgy_mode"] == "llm"
    assert snap["effective"]["director_dramaturgy_mode"] == "llm"
    assert (tmp_path / "runtime_settings.json").is_file()


def test_reset_restores_default(tmp_path: Path) -> None:
    reset_runtime_settings_for_tests(persist_path=tmp_path / "runtime_settings.json")
    default_mode = settings.director_dramaturgy_mode
    apply_runtime_settings({"director_dramaturgy_mode": "llm" if default_mode == "rules" else "rules"})
    apply_runtime_settings(reset=True)
    assert settings.director_dramaturgy_mode == default_mode
    assert get_snapshot()["overrides"] == {}


def test_rejects_unknown_key(tmp_path: Path) -> None:
    reset_runtime_settings_for_tests(persist_path=tmp_path / "runtime_settings.json")
    try:
        apply_runtime_settings({"openai_api_key": "sk-test"})
        raise AssertionError("should reject secrets")
    except ValueError as exc:
        assert "nicht editierbar" in str(exc)


def test_patch_runtime_settings_api(tmp_path: Path) -> None:
    reset_runtime_settings_for_tests(persist_path=tmp_path / "runtime_settings.json")
    res = client.patch(
        "/api/v1/director/runtime-settings",
        json={"values": {"teil2_atmosphere_use_llm": True, "osc_dry_run": True}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["effective"]["teil2_atmosphere_use_llm"] is True
    assert body["overrides"]["osc_dry_run"] is True


def test_get_runtime_settings_api(tmp_path: Path) -> None:
    reset_runtime_settings_for_tests(persist_path=tmp_path / "runtime_settings.json")
    res = client.get("/api/v1/director/runtime-settings")
    assert res.status_code == 200
    body = res.json()
    assert "director_dramaturgy_mode" in body["effective"]
    assert "defaults" in body
