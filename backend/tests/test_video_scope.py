from pathlib import Path

from app.services.video_scope import (
    _clip_ids_for_scope,
    atmosphere_clip_ids,
    build_video_catalog,
    osc_availability_by_clip,
    usable_dramaturgy_video_ids,
)

REPO = Path(__file__).resolve().parents[2]


def test_part1_excludes_narrator_avatar_clips() -> None:
    part1_ids = _clip_ids_for_scope("part1")
    part2_ids = _clip_ids_for_scope("part2")

    assert "clyde" in part1_ids
    assert "inge" not in part1_ids
    assert "sebastian" not in part1_ids
    assert "musiker" not in part1_ids
    assert "random" not in part1_ids
    assert "avatar2" not in part1_ids

    assert "inge" in part2_ids
    assert "clyde" in part2_ids
    assert "random" not in part2_ids
    assert "avatar2" not in part2_ids


def test_part2_marks_avatar_clips() -> None:
    catalog = build_video_catalog("part2")
    by_id = {clip.id: clip for clip in catalog.clips}
    assert by_id["inge"].video_type == "avatar"
    assert by_id["clyde"].video_type == "atmosphere"


def test_part1_clyde_on_all_projectors() -> None:
    availability = osc_availability_by_clip("part1")
    assert availability["clyde"] == {"rz21", "adam", "eva", "led"}


def test_part2_inge_on_all_beamers_in_avatar_list() -> None:
    availability = osc_availability_by_clip("part2")
    assert availability["inge"] == {"rz21", "adam", "eva", "led"}


def test_atmosphere_clip_ids_require_all_beamers(monkeypatch) -> None:
    from app.services import video_scope as scope_mod

    monkeypatch.setattr(
        scope_mod,
        "osc_availability_by_clip",
        lambda scope: {
            "clyde": {"rz21", "adam", "eva", "led"},
            "partial": {"rz21"},
            "random": {"rz21", "adam", "eva", "led"},
            "avatar2": {"rz21", "adam", "eva", "led"},
        },
    )
    pool = atmosphere_clip_ids(avatar_clip_ids=set())
    assert "clyde" in pool
    assert "partial" not in pool
    assert "random" not in pool
    assert "avatar2" not in pool


def test_usable_dramaturgy_keeps_partial_avatar_clips() -> None:
    usable = usable_dramaturgy_video_ids("part2")
    assert "inge" in usable
    assert "sebastian" in usable
    assert "clyde" in usable
    assert "random" not in usable
    assert "avatar2" not in usable


def test_atmosphere_osc_omits_random_and_avatar2() -> None:
    text = (REPO / "media/video/OSCBefehllisteOhneAvatare.txt").read_text(encoding="utf-8")
    assert ".Random" not in text
    assert ".Avatar2" not in text
    for clip in ("Clyde", "Bonnie", "Black"):
        for prefix in ("KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"):
            assert f'"{prefix}.{clip}"' in text
