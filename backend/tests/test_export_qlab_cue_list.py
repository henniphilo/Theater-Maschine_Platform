"""Tests for export_qlab_cue_list.py."""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "export_qlab_cue_list.py"
PROJECTORS = frozenset({"adam", "eva", "led", "rz21"})


def _load_module():
    spec = importlib.util.spec_from_file_location("export_qlab_cue_list", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_rows_includes_all_osc_sources() -> None:
    module = _load_module()
    rows = module.collect_rows()
    sources = {row["source"] for row in rows}
    # Root OSCBefehlliste.txt overlaps atmosphere → merged label database+atmosphere
    assert any(s == "database" or s.startswith("database") for s in sources)
    assert "avatar" in sources
    assert any("atmosphere" in s for s in sources)
    by_projector = Counter(row["projector"] for row in rows)
    assert set(by_projector) == PROJECTORS
    assert len(set(by_projector.values())) == 1
    assert len(rows) == next(iter(by_projector.values())) * len(PROJECTORS)


def test_bak1_qlab_number_matches_osc_list() -> None:
    module = _load_module()
    rows = module.collect_rows()
    match = next(row for row in rows if row["clip_part"] == "BAK1_NicolasPflanzen3" and row["projector"] == "rz21")
    assert match["clip_id"] == "bak1_nicolaspflanzen3"
    assert match["qlab_cue_number"] == "KI_RZ21.BAK1_NicolasPflanzen3"
    assert match["source"] == "avatar"


def test_rz21_subset_matches_other_projectors() -> None:
    module = _load_module()
    rows = [row for row in module.collect_rows() if row["projector"] == "rz21"]
    all_rows = module.collect_rows()
    by_projector = Counter(row["projector"] for row in all_rows)
    assert len(rows) == by_projector["adam"]
    assert by_projector["rz21"] == by_projector["eva"] == by_projector["led"]
