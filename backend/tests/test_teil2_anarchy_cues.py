"""Tests for anarchy-driven Teil-2 keyword cue selection."""

from app.director.cues.cue_models import CuePoint, CuePointTrigger, LightCue, SoundCue
from app.schemas.inszenierung import AnarchyCurve
from app.services.teil2_anarchy_cues import (
    anarchy_at,
    anarchy_for_char_offset,
    anarchy_function,
    apply_anarchy_to_keyword_cue_point,
    build_keyword_cue_point,
    extract_text_fallback_keywords,
    keyword_in_script,
    min_keyword_cues_for_script,
)


def test_anarchy_increases_with_sentence_index() -> None:
    curve = AnarchyCurve(start=0.35, end=1.0)
    assert anarchy_at(0, 10, curve) < anarchy_at(9, 10, curve)


def test_anarchy_increases_with_char_offset() -> None:
    curve = AnarchyCurve(start=0.35, end=1.0)
    script = "Anfang Mitte Ende"
    assert anarchy_for_char_offset(0, len(script), curve) < anarchy_for_char_offset(
        len(script) - 1, len(script), curve
    )


def test_anarchy_function_escalates() -> None:
    assert anarchy_function(0.3) == "verstärken"
    assert anarchy_function(0.9) == "desorientieren"


def test_build_keyword_cue_point_has_sound_or_light() -> None:
    point = build_keyword_cue_point("Schuld", 2, 0.6, slot=1)
    assert point.trigger == CuePointTrigger.KEYWORD
    assert point.keyword == "Schuld"
    assert point.sentence_index == 2
    assert point.sound is not None or point.light is not None


def test_apply_anarchy_to_keyword_strips_visual() -> None:
    script = "Die Schuld bleibt."
    sentences = ["Die Schuld bleibt."]
    point = CuePoint(
        trigger=CuePointTrigger.KEYWORD,
        keyword="Schuld",
        visual={"clip_id": "clyde"},
        sound=SoundCue(cue_id="drone"),
        light=LightCue(scene_id="warm"),
    )
    updated = apply_anarchy_to_keyword_cue_point(
        point, "Schuld", script, sentences, AnarchyCurve()
    )
    assert updated is not None
    assert updated.visual is None
    assert updated.function
    assert updated.sentence_index == 0


def test_extract_text_fallback_keywords_uses_script_surface_only() -> None:
    script = (
        "23. Der Delphin? Man hat mich dazu gezwungen.\n\n"
        "24. Der Bärenklauer übernimmt die Schuld."
    )
    sentences = [
        "23. Der Delphin? Man hat mich dazu gezwungen.",
        "24. Der Bärenklauer übernimmt die Schuld.",
    ]
    curve = AnarchyCurve(start=0.35, end=1.0)
    keywords = extract_text_fallback_keywords(script, sentences, curve, min_keywords=4)
    assert len(keywords) >= 4
    labels = {item[0].lower() for item in keywords}
    assert "delphin" in labels or "bärenklauer" in labels
    assert all(keyword_in_script(keyword, script) for keyword, _, _ in keywords)


def test_keyword_in_script_is_case_insensitive() -> None:
    assert keyword_in_script("Delphin", "Der delphin spricht.")
    assert not keyword_in_script("Wolf", "Der Delphin spricht.")


def test_min_keyword_cues_scales_with_script_length() -> None:
    assert min_keyword_cues_for_script("x" * 100) == 12
    assert min_keyword_cues_for_script("x" * 5000) >= 14
