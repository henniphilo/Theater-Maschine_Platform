"""Tests for QLab light patch installer (dry-run / detection only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "tools" / "qlab_install_light_patch.py"


def _load():
    spec = importlib.util.spec_from_file_location("qlab_install_light_patch", INSTALLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_patch_dry_run_when_missing(monkeypatch) -> None:
    installer = _load()
    monkeypatch.setattr(installer, "_instrument_exists", lambda: False)
    assert installer.install_patch(dry_run=True) == "would-create"


def test_install_patch_dry_run_when_present(monkeypatch) -> None:
    installer = _load()
    monkeypatch.setattr(installer, "_instrument_exists", lambda: True)
    assert installer.install_patch(dry_run=True) == "exists"
