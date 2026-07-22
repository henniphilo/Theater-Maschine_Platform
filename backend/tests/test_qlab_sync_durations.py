"""Tests for tools/qlab_sync_durations.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "qlab_sync_durations.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("qlab_sync_durations", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_qlab_duration_locale_comma() -> None:
    module = _load_module()
    assert module.parse_qlab_duration_seconds("24,16") == 24.16
    assert module.parse_qlab_duration_seconds("20.667") == 20.667
    assert module.parse_qlab_duration_seconds("0") is None
    assert module.parse_qlab_duration_seconds("") is None


def test_seconds_to_ms_rounds() -> None:
    module = _load_module()
    assert module.seconds_to_ms(24.16) == 24160
    assert module.seconds_to_ms(20.667) == 20667
    assert module.seconds_to_ms(32.959) == 32959


def test_build_duration_prefers_rz21() -> None:
    module = _load_module()
    alias_map = {
        module._normalize_key("BAK2_Krabbe"): {"bak2_krabbe"},
    }
    rows = [
        ("KI_Adam.BAK2_Krabbe", "BAK2_Krabbe", 6.5),
        ("KI_RZ21.BAK2_Krabbe", "BAK2_Krabbe", 6.0),
    ]
    durations, notes = module.build_duration_by_clip_id(rows, alias_map)
    assert durations["bak2_krabbe"] == 6000
    assert any("disagree" in note for note in notes)


def test_duration_lookup_by_scene_ref() -> None:
    module = _load_module()
    durations = {"bak1_nicolaspflanzen3": 24160}
    assert module.duration_lookup(durations, "BAK1_NicolasPflanzen3") == 24160
    assert module.duration_lookup(durations, "bak1_nicolaspflanzen3") == 24160
