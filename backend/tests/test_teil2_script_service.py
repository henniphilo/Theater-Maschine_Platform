"""Tests for Teil-2 script timeline from avatar CSV."""

from __future__ import annotations

from app.schemas.avatar_speech import AvatarSpeechCue
from app.schemas.inszenierung import AnarchyCurve
from app.services.avatar_duration import resolve_avatar_beat_duration_ms
from app.services.teil2_script_service import (
    build_beat_previews,
    build_timeline_from_csv,
    group_catalog_cues_into_beats,
    validate_cues_against_script,
)


def _cue(
    cue_id: str,
    text: str,
    avatar: str = "delphin",
    clip: str = "avatar",
    duration_ms: int | None = None,
) -> AvatarSpeechCue:
    return AvatarSpeechCue(
        id=cue_id,
        avatar=avatar,
        text=text,
        video_clip_id=clip,
        duration_ms=duration_ms,
    )


def test_resolve_avatar_beat_duration_prefers_numbers_over_text():
    cues = [_cue("DEL1", "Kurz.", duration_ms=420_000)]
    resolved = resolve_avatar_beat_duration_ms("Kurz.", cues)
    assert resolved == 420_000


def test_resolve_avatar_beat_duration_chorus_uses_max_layer():
    cues = [
        _cue("DEL1", "Chorus.", duration_ms=90_000),
        _cue("LG1", "Chorus.", avatar="lamm", clip="esel", duration_ms=540_000),
    ]
    resolved = resolve_avatar_beat_duration_ms("Chorus.", cues)
    assert resolved == 540_000


def test_build_timeline_uses_resolved_duration_on_moment_and_visual_cue():
    script = "23. Der Delphin? Man hat mich dazu gezwungen."
    cues = [_cue("DEL1", "23. Der Delphin? Man hat mich dazu gezwungen.", duration_ms=420_000)]
    plan = build_timeline_from_csv(
        anarchy_curve=AnarchyCurve(start=0.2, end=0.2),
        script_text=script,
        cues=cues,
    )
    moment = plan.moments[0]
    assert moment.duration_hint_ms == 420_000
    assert moment.avatar_layers[0].visual_cue is not None
    assert moment.avatar_layers[0].visual_cue.duration_ms == 420_000


def test_group_consecutive_duplicate_text_as_chorus():
    cues = [
        _cue("DEL1", "Gleicher Text.", "delphin"),
        _cue("LG1", "Gleicher Text.", "lamm", "esel"),
        _cue("WO1", "Anderer Text.", "wolf", "thiel"),
    ]
    groups = group_catalog_cues_into_beats(cues)
    assert len(groups) == 2
    assert len(groups[0].cues) == 2
    assert groups[0].cues[0].id == "DEL1"
    assert groups[0].cues[1].id == "LG1"


def test_build_timeline_avatar_video_all_beats():
    script = (
        "23. Der Delphin? Man hat mich dazu gezwungen.\n\n"
        "24. Der Bärenklauer übernimmt.\n\n"
        "25. Das Lamm Gottes,\n"
    )
    cues = [
        _cue("DEL1", "23. Der Delphin? Man hat mich dazu gezwungen."),
        _cue("BK1", "24. Der Bärenklauer übernimmt.", "baerenklau", "avatar2"),
        _cue("LG1", "25. Das Lamm Gottes,", "lamm", "esel"),
    ]
    plan = build_timeline_from_csv(
        anarchy_curve=AnarchyCurve(start=0.2, end=0.8),
        script_text=script,
        cues=cues,
    )

    assert len(plan.moments) == 3
    assert all(m.speech_mode == "avatar_video" for m in plan.moments)
    assert plan.moments[0].avatar_layers[0].avatar_speech_id == "DEL1"
    assert plan.moments[-1].anarchy_level >= plan.moments[0].anarchy_level


def test_validate_cues_against_script_warns_on_missing():
    script = "Nur ein bekannter Text."
    cues = [_cue("DEL1", "Unbekannter Avatar-Textabschnitt hier.")]
    warnings = validate_cues_against_script(cues, script)
    assert len(warnings) == 1


def test_real_catalog_previews_match_csv_row_count():
    previews = build_beat_previews()
    assert len(previews) >= 33
    assert previews[0].avatar_ids[0] == "nicolas"
