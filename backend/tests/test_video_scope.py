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
            "bitcoinfahrt": {"rz21", "adam", "eva", "led"},
            "clyde": {"rz21", "adam", "eva", "led"},
            "ipad": {"rz21", "adam", "eva", "led"},
            "macbook": {"rz21", "adam", "eva", "led"},
            "inge": {"rz21", "adam", "eva", "led"},
            "thiemo": {"rz21", "adam", "eva", "led"},
            "thomas": {"rz21", "adam", "eva", "led"},
            "sebastian": {"rz21", "adam", "eva", "led"},
            "branko": {"rz21", "adam", "eva", "led"},
            "partial": {"rz21"},
            "random": {"rz21", "adam", "eva", "led"},
            "avatar2": {"rz21", "adam", "eva", "led"},
        },
    )
    pool = atmosphere_clip_ids(avatar_clip_ids=set())
    assert "bitcoinfahrt" in pool
    assert "clyde" in pool  # recurring stage rule
    assert "ipad" not in pool
    assert "macbook" not in pool
    assert "inge" not in pool
    assert "thiemo" not in pool
    assert "thomas" not in pool
    assert "sebastian" not in pool
    assert "branko" not in pool
    assert "partial" not in pool
    assert "random" not in pool
    assert "avatar2" not in pool


def test_atmosphere_clip_ids_match_staging_allowlist() -> None:
    from app.services.video_scope import ACTIVE_ATMOSPHERE_CLIP_IDS

    pool = atmosphere_clip_ids(avatar_clip_ids=set())
    assert pool
    assert pool <= ACTIVE_ATMOSPHERE_CLIP_IDS
    assert "bitcoinfahrt" in pool
    assert "clyde" in pool
    assert "bonnie" in pool
    assert "black" not in pool


def test_merge_video_catalog_does_not_strip_avatar_osc_clips(monkeypatch, tmp_path) -> None:
    """removed=True on Begleitvideo cleanup must not drop CSV avatar clips."""
    from app.schemas.extra_media import CueOverrideFlags, ExtraMediaOverrides, VideoKindOverlay
    from app.schemas.video_cues import VideoClipEntry, VideoCueCatalog
    from app.services import extra_media_overrides as emo

    overrides = ExtraMediaOverrides(
        videos=VideoKindOverlay(
            overrides={
                "bak1_nicolaspflanzen3": CueOverrideFlags(dramaturgy_active=False, removed=True),
                "black": CueOverrideFlags(dramaturgy_active=False, removed=True),
            }
        )
    )
    monkeypatch.setattr(emo, "load_overrides", lambda force=False: overrides)
    monkeypatch.setattr(
        "app.services.video_scope._avatar_clip_ids",
        lambda: {"bak1_nicolaspflanzen3"},
    )

    catalog = VideoCueCatalog(
        clips=[
            VideoClipEntry(
                id="bak1_nicolaspflanzen3",
                pixera_name="BAK1_NicolasPflanzen3",
                label="BAK1",
                video_type="avatar",
            ),
            VideoClipEntry(
                id="black",
                pixera_name="Black",
                label="Black",
                video_type="atmosphere",
            ),
        ]
    )
    merged = emo.merge_video_catalog(catalog)
    ids = {clip.id for clip in merged.clips}
    assert "bak1_nicolaspflanzen3" in ids
    assert "black" not in ids


def test_usable_dramaturgy_keeps_partial_avatar_clips() -> None:
    usable = usable_dramaturgy_video_ids("part2")
    assert "inge" in usable
    assert "sebastian" in usable
    assert "bitcoinfahrt" in usable
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
