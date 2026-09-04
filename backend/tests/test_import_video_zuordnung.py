"""Tests for atmosphere video Numbers import."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.import_video_zuordnung import (
    EXCLUDED_ATMOSPHERE_PIXERA,
    numbers_clip_to_pixera,
    parse_existing_osc_by_prefix,
    parse_numbers_sheet_duration_ms,
    slug_id,
)


def test_numbers_clip_to_pixera_atmosphere_names() -> None:
    assert numbers_clip_to_pixera("Bitcoinfahrt") == "Bitcoinfahrt"
    assert numbers_clip_to_pixera("Affen Slow_Odysee 2001") == "AffenSlowOdysee"
    assert numbers_clip_to_pixera("Hier unter der Erde") == "HierUnterDerErde"
    assert numbers_clip_to_pixera("Bitcoin_and_worm") == "Bitcoin_and_worm"
    assert numbers_clip_to_pixera("Brennender_Wald") == "Brennender_Wald"
    assert numbers_clip_to_pixera("Schmetterlinge_laufen") == "Schmetterlinge_laufen"
    assert numbers_clip_to_pixera("Flut") == "Flut"
    assert numbers_clip_to_pixera("Massenproduktion") == "Massenproduktion"
    assert numbers_clip_to_pixera("Konzeptionsprobe_2 Test_030926") == "Konzeptionsprobe_2_Test_030926"
    assert numbers_clip_to_pixera("Konzeptionsprobe_3 Test_030926") == "Konzeptionsprobe_3_Test_030926"
    assert numbers_clip_to_pixera("Haut und Ameisen") == "HautUndAmeisen"
    assert numbers_clip_to_pixera("Skorpione_rennen_nach_Geld") == "Skorpione_rennen_nach_Geld"


def test_slug_id_from_pixera() -> None:
    assert slug_id("FischUndWassergewaechs") == "fischundwassergewaechs"
    assert slug_id("Bitcoin_and_worm") == "bitcoin_and_worm"


def test_parse_numbers_sheet_duration_mm_ss() -> None:
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 0, 22, 0)) == 22_000
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 1, 33, 0)) == 93_000
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 3, 16, 0)) == 196_000
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 18, 40, 0)) == 1_120_000


def test_parse_existing_osc_drops_random_and_avatar2(tmp_path: Path) -> None:
    path = tmp_path / "osc.txt"
    path.write_text(
        '("/pixera/args/cue/apply", "KI_RZ21.Clyde")\n'
        '("/pixera/args/cue/apply", "KI_RZ21.Random")\n'
        '("/pixera/args/cue/apply", "KI_RZ21.Avatar2")\n',
        encoding="utf-8",
    )
    by_prefix = parse_existing_osc_by_prefix(path)
    assert by_prefix["KI_RZ21"] == ["Clyde"]
    assert EXCLUDED_ATMOSPHERE_PIXERA == frozenset({"Random", "Avatar2"})
