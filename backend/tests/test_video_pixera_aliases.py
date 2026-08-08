"""Tests for catalog ↔ OSC pixera name aliases."""

from pathlib import Path
import re

import pytest

from app.schemas.video_cues import VideoClipEntry
from app.services.video_cue_catalog import get_video_cue_catalog_service
from app.services.video_pixera_aliases import (
    CATALOG_TO_OSC_PIXERA,
    catalog_pixera_to_osc_name,
    osc_pixera_to_catalog_name,
)
from app.services.video_scope import _clip_id_for_pixera_name, _name_to_id_map

REPO = Path(__file__).resolve().parents[2]


def _osc_clip_names() -> set[str]:
    names: set[str] = set()
    for rel in (
        "media/video/OSCBefehllisteAvatare.txt",
        "media/video/OSCBefehllisteOhneAvatare.txt",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        for match in re.finditer(r'\("/pixera/args/cue/apply",\s*"[^"]+\.([^"]+)"\)', text):
            names.add(match.group(1))
    return names


def test_ipad_alias_resolves_to_osc_name() -> None:
    assert catalog_pixera_to_osc_name("Ipad") == "IPad"


def test_avatar_catalog_names_pass_through_to_osc_lists() -> None:
    """Former broken aliases must not rewrite names already present in OSC lists."""
    for catalog_name in (
        "BAK1_NicolasPflanzen3",
        "BK0_Waran",
        "MO1_SebMusik",
        "MO3_Caro",
        "PET0_Baer_Thomas",
        "SCH2_Azaria_als_Schaf",
        "SCH2_AzariawirdSchaf",
        "SCH3_IngewirdSchaf",
        "SCH5_SchafSolo_Mavie",
        "SCH7_Schaf_Single_Sebastian",
        "SCH8_Viele_Schafe_Caro",
    ):
        assert catalog_pixera_to_osc_name(catalog_name) == catalog_name


def test_all_send_aliases_exist_in_osc_lists() -> None:
    osc = _osc_clip_names()
    for catalog_name, osc_name in CATALOG_TO_OSC_PIXERA.items():
        assert osc_name in osc, f"{catalog_name} → {osc_name} missing from OSC lists"


def test_legacy_osc_name_maps_back_to_catalog_clip_id() -> None:
    clips = [
        VideoClipEntry(
            id="bak1_nicolaspflanzen3",
            pixera_name="BAK1_NicolasPflanzen3",
        )
    ]
    name_to_id = _name_to_id_map(clips)
    assert _clip_id_for_pixera_name("BAK1_NicolasPflanzen3", name_to_id) == "bak1_nicolaspflanzen3"
    assert osc_pixera_to_catalog_name("BAK1_Nicolas_Pflanzen") == "BAK1_NicolasPflanzen3"
    assert _clip_id_for_pixera_name("BAK1_Nicolas_Pflanzen", name_to_id) == "bak1_nicolaspflanzen3"


def test_pixera_cue_name_matches_osc_list_spelling() -> None:
    assert (
        f"KI_Adam.{catalog_pixera_to_osc_name('BAK1_NicolasPflanzen3')}"
        == "KI_Adam.BAK1_NicolasPflanzen3"
    )
    assert f"KI_Adam.{catalog_pixera_to_osc_name('Ipad')}" == "KI_Adam.IPad"


def test_part2_cues_resolve_against_real_osc_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ignore conftest fixture OSC redirect for this integration check."""
    from app.services import video_scope as scope_mod

    def _real_osc_paths(scope: str):
        avatars = REPO / "media/video/OSCBefehllisteAvatare.txt"
        atmos = REPO / "media/video/OSCBefehllisteOhneAvatare.txt"
        if scope == "part1":
            return [p for p in (atmos,) if p.is_file()]
        return [p for p in (atmos, avatars) if p.is_file()]

    monkeypatch.setattr(scope_mod, "_osc_paths_for_scope", _real_osc_paths)
    service = get_video_cue_catalog_service()
    service.clear_cache()
    catalog = service.load("part2")
    osc = _osc_clip_names()
    missing = [
        f"{clip.id}:{clip.pixera_name}->{catalog_pixera_to_osc_name(clip.pixera_name)}"
        for clip in catalog.clips
        if catalog_pixera_to_osc_name(clip.pixera_name) not in osc
    ]
    assert missing == []
    bak = next(c for c in catalog.clips if c.pixera_name == "BAK1_NicolasPflanzen3")
    assert service.pixera_cue_name("adam", bak.id, catalog, scope="part2") == (
        "KI_Adam.BAK1_NicolasPflanzen3"
    )
