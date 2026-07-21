"""Tests for QLab light cue list export and simulation colors."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def _load_tool(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qlab_light_sim = _load_tool("qlab_light_sim", TOOLS / "qlab_light_sim.py")


def test_sim_color_blackout_is_zero() -> None:
    red, green, blue, intensity = qlab_light_sim.sim_color_for_scene({"id": "blackout", "moods": []})
    assert (red, green, blue, intensity) == (0, 0, 0, 0)


def test_build_command_text_uses_tm_preview() -> None:
    text = qlab_light_sim.build_command_text(
        {
            "id": "saallicht",
            "moods": ["saal"],
            "channels": [],
            "groups": ["2"],
            "intensity_max": 1.0,
        }
    )
    assert "TMPREVIEW.red" in text
    assert "TMPREVIEW.intensity" in text
    for line in text.splitlines():
        value = int(line.split("=")[1].strip())
        assert 0 <= value <= 100, line


def test_export_qlab_light_cue_list_writes_csv(tmp_path, monkeypatch) -> None:
    scenes_path = tmp_path / "light_scenes.json"
    scenes_path.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "saallicht",
                        "description": "Saallicht",
                        "channels": [],
                        "groups": ["2"],
                        "fade_time": 4.0,
                        "moods": ["saal"],
                        "intensity_max": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "qlab_light_cue_list.csv"

    script_path = ROOT / "backend" / "scripts" / "export_qlab_light_cue_list.py"
    spec = importlib.util.spec_from_file_location("export_qlab_light_cue_list", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(TOOLS))
    spec.loader.exec_module(module)

    rows = module.export_rows(module._load_scenes(scenes_path))
    module.write_csv(rows, out_path)

    with out_path.open(encoding="utf-8", newline="") as handle:
        parsed = list(csv.DictReader(handle))
    assert len(parsed) == 1
    assert parsed[0]["qlab_cue_number"] == "saallicht"
    assert parsed[0]["groups"] == "2"
