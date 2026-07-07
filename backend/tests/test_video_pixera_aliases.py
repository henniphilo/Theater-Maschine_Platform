"""Tests for catalog ↔ OSC pixera name aliases."""

from app.schemas.video_cues import VideoClipEntry
from app.services.video_cue_catalog import get_video_cue_catalog_service
from app.services.video_pixera_aliases import catalog_pixera_to_osc_name
from app.services.video_scope import _clip_id_for_pixera_name, _name_to_id_map


def test_bak1_pixera_alias_resolves_to_osc_name() -> None:
    assert catalog_pixera_to_osc_name("BAK1_NicolasPflanzen3") == "BAK1_Nicolas_Pflanzen"


def test_osc_pixera_name_maps_back_to_catalog_clip_id() -> None:
    clips = [
        VideoClipEntry(
            id="bak1_nicolaspflanzen3",
            pixera_name="BAK1_NicolasPflanzen3",
        )
    ]
    name_to_id = _name_to_id_map(clips)
    assert _clip_id_for_pixera_name("BAK1_Nicolas_Pflanzen", name_to_id) == "bak1_nicolaspflanzen3"


def test_pixera_cue_name_uses_osc_alias() -> None:
    service = get_video_cue_catalog_service()
    service.clear_cache()
    catalog = service.load("part2")
    clip = service.clip_by_id("bak1_nicolaspflanzen3", catalog, scope="part2")
    if clip is None:
        clip = next((c for c in catalog.clips if c.pixera_name == "BAK1_NicolasPflanzen3"), None)
    if clip is None:
        return
    name = service.pixera_cue_name("adam", clip.id, catalog, scope="part2")
    assert name == "KI_Adam.BAK1_Nicolas_Pflanzen"
