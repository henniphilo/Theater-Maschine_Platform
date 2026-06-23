
from app.services.avatar_speech_catalog import (
    match_avatar_cues,
    normalize_avatar_text,
    parse_avatar_csv,
    resolve_avatar_csv_path,
)


def test_avatar_csv_loads_and_maps_prefixes() -> None:
    path = resolve_avatar_csv_path()
    assert path is not None
    catalog = parse_avatar_csv(path)
    assert len(catalog.cues) >= 30
    del_cue = next(c for c in catalog.cues if c.id == "DEL1")
    assert del_cue.avatar == "delphin"
    assert del_cue.video_clip_id == "avatar"
    bk_cue = next(c for c in catalog.cues if c.id == "BK1")
    assert bk_cue.avatar == "baerenklau"
    assert bk_cue.video_clip_id == "avatar2"


def test_pet5_duplicate_gets_suffix() -> None:
    path = resolve_avatar_csv_path()
    assert path is not None
    catalog = parse_avatar_csv(path)
    pet_ids = [c.id for c in catalog.cues if c.id.startswith("PET5")]
    assert "PET5" in pet_ids
    assert "PET5a" in pet_ids


def test_normalize_avatar_text_strips_control_chars() -> None:
    assert "_x000B_" not in normalize_avatar_text("Geld_x000B_könnte")


def test_match_avatar_cues_finds_overlap() -> None:
    path = resolve_avatar_csv_path()
    assert path is not None
    catalog = parse_avatar_csv(path)
    bk3 = next(c for c in catalog.cues if c.id == "BK3")
    matches = match_avatar_cues(bk3.text[:80])
    assert any(m.id == "BK3" for m in matches)
