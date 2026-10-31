"""Tests for anarchy-driven Teil-2 keyword cue selection."""

from app.director.cues.cue_models import CuePoint, CuePointTrigger, LightCue, SoundCue
from app.schemas.inszenierung import AnarchyCurve
from app.services.teil2_anarchy_cues import (
    KEYWORD_CUES_PER_SENTENCE,
    anarchy_at,
    anarchy_for_char_offset,
    anarchy_function,
    apply_anarchy_to_keyword_cue_point,
    balance_keyword_cue_points,
    build_keyword_cue_point,
    densify_keyword_sound_cues,
    diversify_keyword_sound_cues,
    extract_text_fallback_keywords,
    is_playable_sound_id,
    keyword_in_script,
    min_keyword_cues_for_script,
    pick_sound_id,
    playable_dramaturgy_sounds,
    playable_sound_pool,
    sound_volume_for_anarchy,
    teil2_cue_allowlist,
    thin_keyword_sound_cues,
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


def test_build_keyword_cue_point_has_playable_sound() -> None:
    point = build_keyword_cue_point("Schuld", 2, 0.6, slot=1)
    assert point.trigger == CuePointTrigger.KEYWORD
    assert point.keyword == "Schuld"
    assert point.sentence_index == 2
    assert point.sound is not None
    assert is_playable_sound_id(point.sound.cue_id)
    assert point.sound.volume == sound_volume_for_anarchy(0.6)


def test_early_light_fade_is_longer_than_chaos_fade() -> None:
    early = build_keyword_cue_point("Anfang", 0, 0.3, slot=0)
    late = build_keyword_cue_point("Chaos", 20, 0.95, slot=20)
    if early.light and late.light:
        assert early.light.fade_time >= late.light.fade_time


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


def test_extract_fallback_spreads_keywords_across_sentences() -> None:
    """Long first sentence must not hoard more than KEYWORD_CUES_PER_SENTENCE."""
    long = (
        "21. Der Bärenklau: Pflanzen Schuld Maschine Puls Tausch Bruch Nachhall "
        "Erinnerung Glitch Käfig Echo Metall."
    )
    short = [
        "Der Delphin spricht.",
        "Das Lamm bleibt.",
        "Der Wolf wartet.",
        "Die Krabbe flieht.",
    ]
    script = " ".join([long, *short])
    sentences = [long, *short]
    curve = AnarchyCurve(start=0.35, end=1.0)
    keywords = extract_text_fallback_keywords(
        script, sentences, curve, min_keywords=8, max_keywords=40
    )
    from collections import Counter

    per_sentence = Counter(sent_idx for _, sent_idx, _ in keywords)
    assert per_sentence
    assert max(per_sentence.values()) <= KEYWORD_CUES_PER_SENTENCE
    assert len(per_sentence) >= 3


def test_balance_keyword_cue_points_caps_per_sentence() -> None:
    points = [
        build_keyword_cue_point("eins", 0, 0.4, slot=0),
        build_keyword_cue_point("zwei", 0, 0.4, slot=1),
        build_keyword_cue_point("drei", 0, 0.4, slot=2),
        build_keyword_cue_point("vier", 1, 0.5, slot=3),
    ]
    balanced = balance_keyword_cue_points(points, max_per_sentence=2)
    from collections import Counter

    counts = Counter(point.sentence_index or 0 for point in balanced)
    assert counts[0] == 2
    assert counts[1] == 1
    assert all(
        point.sound and is_playable_sound_id(point.sound.cue_id) for point in balanced
    )


def test_keyword_in_script_is_case_insensitive() -> None:
    assert keyword_in_script("Delphin", "Der delphin spricht.")
    assert not keyword_in_script("Wolf", "Der Delphin spricht.")


def test_min_keyword_cues_scales_with_script_length() -> None:
    assert min_keyword_cues_for_script("x" * 100) == 20
    assert min_keyword_cues_for_script("x" * 5000) >= 27


def test_allowlist_and_picks_use_full_play_pool() -> None:
    allowlist = teil2_cue_allowlist()
    assert allowlist["sounds"]
    assert all(item["action"] == "play" for item in allowlist["sounds"])
    from app.director.media.database import MediaDatabase

    db = MediaDatabase()
    playable = playable_sound_pool(db)
    assert playable
    assert all(sound.action == "play" for sound in playable)
    allowlist_ids = {item["id"] for item in allowlist["sounds"]}
    assert allowlist_ids == {sound.id for sound in playable}
    # Full catalog play cues, not only dramaturgy_active subset.
    assert len(playable) >= len(playable_dramaturgy_sounds(db.dramaturgy_sounds))
    assert "stallluft_digital" in allowlist_ids


def test_pick_sound_id_cycles_through_pool() -> None:
    pool = playable_sound_pool()
    assert len(pool) >= 4
    recent: list[str] = []
    picked: list[str] = []
    for slot in range(len(pool)):
        cue_id = pick_sound_id(slot, 0.5, pool, recent=recent)
        assert cue_id is not None
        assert is_playable_sound_id(cue_id)
        picked.append(cue_id)
        recent.append(cue_id)
    assert len(set(picked)) == len(pool)


def test_apply_anarchy_replaces_stop_sound_with_play() -> None:
    script = "Die Schuld bleibt."
    sentences = ["Die Schuld bleibt."]
    point = CuePoint(
        trigger=CuePointTrigger.KEYWORD,
        keyword="Schuld",
        sound=SoundCue(cue_id="kaefigecho_out"),
    )
    updated = apply_anarchy_to_keyword_cue_point(
        point, "Schuld", script, sentences, AnarchyCurve()
    )
    assert updated is not None
    assert updated.sound is not None
    assert is_playable_sound_id(updated.sound.cue_id)
    assert updated.sound.volume >= 0.58


def test_densify_fills_wide_sound_gaps_between_sentences() -> None:
    sentences = [
        "Der Delphin spricht zuerst.",
        "Dann kommt der Bärenklauer.",
        "Das Lamm bleibt stumm.",
        "Die Maschine räumt die Schuld.",
        "Niemand hört den Puls.",
        "Am Ende bleibt nur Tausch.",
        "Noch ein Satz ohne Klang.",
        "Und noch einer danach.",
        "Dann endlich der Bruch.",
        "Zum Schluss der Nachhall.",
    ]
    script = " ".join(sentences)
    curve = AnarchyCurve(start=0.35, end=1.0)
    sparse = [
        build_keyword_cue_point("Delphin", 0, 0.35, slot=0),
    ]
    dense = densify_keyword_sound_cues(sparse, script, sentences, curve)
    sound_points = [
        point for point in dense if point.sound and is_playable_sound_id(point.sound.cue_id)
    ]
    assert len(sound_points) > 1
    indexes = sorted(point.sentence_index or 0 for point in sound_points)
    gaps = [right - left for left, right in zip(indexes, indexes[1:])]
    assert gaps
    assert max(gaps) <= 5


def test_thin_keyword_sound_cues_keeps_light_and_widens_gaps() -> None:
    points = [
        CuePoint(
            trigger=CuePointTrigger.KEYWORD,
            keyword="eins",
            sentence_index=0,
            sound=SoundCue(cue_id="maschinen_grundader"),
            light=LightCue(scene_id="warme_buehnenflaeche"),
        ),
        CuePoint(
            trigger=CuePointTrigger.KEYWORD,
            keyword="zwei",
            sentence_index=2,
            sound=SoundCue(cue_id="kaefigecho"),
            light=LightCue(scene_id="gegenlicht_weich"),
        ),
        CuePoint(
            trigger=CuePointTrigger.KEYWORD,
            keyword="drei",
            sentence_index=6,
            sound=SoundCue(cue_id="drone"),
            light=LightCue(scene_id="saallicht"),
        ),
    ]
    thinned = thin_keyword_sound_cues(points, min_gap_sentences=4)
    assert thinned[0].sound is not None
    assert thinned[0].light is not None
    assert thinned[1].sound is None
    assert thinned[1].light is not None
    assert thinned[2].sound is not None
    sound_indexes = [
        point.sentence_index or 0
        for point in thinned
        if point.sound and is_playable_sound_id(point.sound.cue_id)
    ]
    assert sound_indexes == [0, 6]


def test_diversify_keyword_sound_cues_avoids_consecutive_repeats() -> None:
    points = [
        CuePoint(
            trigger=CuePointTrigger.KEYWORD,
            keyword="eins",
            sentence_index=0,
            sound=SoundCue(cue_id="maschinen_grundader"),
        ),
        CuePoint(
            trigger=CuePointTrigger.KEYWORD,
            keyword="zwei",
            sentence_index=5,
            sound=SoundCue(cue_id="maschinen_grundader"),
        ),
        CuePoint(
            trigger=CuePointTrigger.KEYWORD,
            keyword="drei",
            sentence_index=10,
            sound=SoundCue(cue_id="maschinen_grundader"),
        ),
    ]
    diversified = diversify_keyword_sound_cues(points)
    ids = [
        point.sound.cue_id
        for point in diversified
        if point.sound and is_playable_sound_id(point.sound.cue_id)
    ]
    assert len(ids) == 3
    assert ids[0] != ids[1]
    assert ids[1] != ids[2]
    assert len(set(ids)) >= 2
