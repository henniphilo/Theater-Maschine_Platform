"""Tests for extra media cue overlays (Einstellungen / cue-admin)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.director.dramaturgy.llm_director import LLMDirector
from app.director.media.database import MediaDatabase
from app.main import app
from app.schemas.extra_media import (
    CueAdminPatchRequest,
    ExtraLightCreateRequest,
    ExtraSoundCreateRequest,
    ExtraVideoCreateRequest,
)
from app.services import extra_media_overrides as extra_media
from app.services.sound_cue_catalog import get_sound_cue_catalog_service
from app.services.video_cue_catalog import get_video_cue_catalog_service
from app.services.video_scope import osc_availability_by_clip

client = TestClient(app)


def test_add_extra_video_persists_and_merges(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    get_video_cue_catalog_service().clear_cache()

    entry = extra_media.add_extra_video(
        ExtraVideoCreateRequest(pixera_name="MeinTestClip", projectors=["rz21"])
    )
    assert entry.id == "meintestclip"
    assert (tmp_path / "extra_media_overrides.json").is_file()

    get_video_cue_catalog_service().clear_cache()
    catalog = get_video_cue_catalog_service().load("part2")
    assert any(c.id == "meintestclip" for c in catalog.clips)

    availability = osc_availability_by_clip("part2")
    assert availability.get("meintestclip") == {"rz21"}


def test_extra_video_all_projectors(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    get_video_cue_catalog_service().clear_cache()
    extra_media.add_extra_video(ExtraVideoCreateRequest(pixera_name="AlleBeamerClip", projectors=["*"]))
    get_video_cue_catalog_service().clear_cache()
    availability = osc_availability_by_clip("part2")
    catalog = get_video_cue_catalog_service().load("part2")
    assert availability["allebeamerclip"] == {p.id for p in catalog.projectors}


def test_llm_lock_excludes_video_and_light(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    get_video_cue_catalog_service().clear_cache()

    extra_media.add_extra_video(ExtraVideoCreateRequest(pixera_name="LockedClip", projectors=["*"]))
    extra_media.add_extra_light(
        ExtraLightCreateRequest(id="locked_light", description="Locked", channels=["99"])
    )
    extra_media.patch_cue("video", "lockedclip", CueAdminPatchRequest(dramaturgy_active=False))
    extra_media.patch_cue("light", "locked_light", CueAdminPatchRequest(dramaturgy_active=False))
    get_video_cue_catalog_service().clear_cache()

    director = LLMDirector(media_db=MediaDatabase())
    allow = director.catalog_allowlist(compact=True)
    video_ids = {v["id"] for v in allow["videos"]}
    light_ids = {s["id"] for s in allow["lights"]}
    assert "lockedclip" not in video_ids
    assert "locked_light" not in light_ids

    # Still in merged catalog for manual/Technik use
    catalog = get_video_cue_catalog_service().load("part2")
    assert any(c.id == "lockedclip" for c in catalog.clips)
    assert any(s.id == "locked_light" for s in MediaDatabase().light_scenes)


def test_removed_excludes_from_catalog_and_availability(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    get_video_cue_catalog_service().clear_cache()
    extra_media.add_extra_video(ExtraVideoCreateRequest(pixera_name="GoneClip", projectors=["adam"]))
    extra_media.patch_cue("video", "goneclip", CueAdminPatchRequest(removed=True))
    get_video_cue_catalog_service().clear_cache()

    catalog = get_video_cue_catalog_service().load("part2")
    assert all(c.id != "goneclip" for c in catalog.clips)
    assert "goneclip" not in osc_availability_by_clip("part2")


def test_extra_sound_requires_midi_and_merges(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    entry = extra_media.add_extra_sound(
        ExtraSoundCreateRequest(soundname="Regen Loop", midi_note=77)
    )
    assert entry.midi_note == 77
    cues = get_sound_cue_catalog_service().load().cues
    match = next(c for c in cues if c.id == "regen_loop")
    assert match.midi_note == 77
    assert match.dramaturgy_active is True
    assert "Note 77" in match.ableton_hint


def test_cue_admin_api_roundtrip(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    get_video_cue_catalog_service().clear_cache()

    res = client.post(
        "/api/v1/media/cue-admin/video",
        json={"pixera_name": "ApiClip", "projectors": ["eva", "led"]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["id"] == "apiclip"

    res = client.post(
        "/api/v1/media/cue-admin/sound",
        json={"soundname": "ApiSound", "midi_note": 42},
    )
    assert res.status_code == 200, res.text

    res = client.post(
        "/api/v1/media/cue-admin/light",
        json={"id": "api_light", "description": "API Light", "channels": ["11-19"]},
    )
    assert res.status_code == 200, res.text

    res = client.patch(
        "/api/v1/media/cue-admin/sound/apisound",
        json={"dramaturgy_active": False},
    )
    assert res.status_code == 200

    res = client.get("/api/v1/media/cue-admin")
    assert res.status_code == 200
    body = res.json()
    video = next(v for v in body["videos"] if v["id"] == "apiclip")
    assert set(video["projectors"]) == {"eva", "led"}
    sound = next(s for s in body["sounds"] if s["id"] == "apisound")
    assert sound["dramaturgy_active"] is False
    assert sound["midi_note"] == 42
    assert any(row["id"] == "api_light" for row in body["lights"])

    res = client.delete("/api/v1/media/cue-admin/video/apiclip")
    assert res.status_code == 200
    get_video_cue_catalog_service().clear_cache()
    assert all(c.id != "apiclip" for c in get_video_cue_catalog_service().load("part2").clips)


def test_delete_catalog_entry_rejected(tmp_path: Path) -> None:
    extra_media.reset_extra_media_for_tests(persist_path=tmp_path / "extra_media_overrides.json")
    res = client.delete("/api/v1/media/cue-admin/sound/maschinen_grundader")
    assert res.status_code == 400
