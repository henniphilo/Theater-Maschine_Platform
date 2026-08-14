from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, VisualCue
from app.schemas.inszenierung import AnarchyCurve, AvatarSpeechLayer, AvatarTextSegment, Gesamtkonzept
from app.services.atmosphere_required_clips import (
    REQUIRED_RECURRING_ATMOSPHERE_CLIPS,
    count_atmosphere_clip,
    ensure_recurring_atmosphere_clips,
    min_recurring_appearances,
    pick_recurring_or_pool_clip,
)
from app.services.teil2_atmosphere_scheduler import (
    AvatarWindow,
    Teil2AtmosphereScheduler,
    build_avatar_windows,
    estimate_script_duration_sec,
)


def test_pick_recurring_alternates_bonnie_clyde() -> None:
    pool = ["strand", "bonnie", "clyde", "black"]
    assert pick_recurring_or_pool_clip(pool, 0) == "bonnie"
    assert pick_recurring_or_pool_clip(pool, 3) == "clyde"
    assert pick_recurring_or_pool_clip(pool, 4) == "strand"


def test_ensure_injects_bonnie_and_clyde_several_times() -> None:
    points = ensure_recurring_atmosphere_clips(
        [],
        windows=[],
        total_sec=120.0,
        allowed_clips={"bonnie", "clyde", "strand", "black"},
    )
    min_each = min_recurring_appearances(120.0)
    assert count_atmosphere_clip(points, "bonnie") >= min_each
    assert count_atmosphere_clip(points, "clyde") >= min_each
    assert {p.visual.clip_id for p in points if p.visual} >= set(REQUIRED_RECURRING_ATMOSPHERE_CLIPS)


def test_ensure_skips_missing_catalog_clips() -> None:
    points = ensure_recurring_atmosphere_clips(
        [],
        windows=[],
        total_sec=90.0,
        allowed_clips={"strand"},
    )
    assert points == []


def test_ensure_does_not_occupy_avatar_beamer() -> None:
    windows = [
        AvatarWindow(start_sec=0.0, end_sec=200.0, projectors=frozenset({"rz21"})),
    ]
    existing = [
        CuePoint(
            trigger=CuePointTrigger.TIME,
            time_offset_sec=20.0,
            visual=VisualCue(clip_id="strand", projector="adam", video_type="atmosphere"),
        )
    ]
    points = ensure_recurring_atmosphere_clips(
        existing,
        windows=windows,
        total_sec=120.0,
        allowed_clips={"bonnie", "clyde", "strand"},
    )
    for point in points:
        assert point.visual is not None
        assert point.visual.projector != "rz21"


def test_rule_atmosphere_includes_bonnie_and_clyde(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    script = "A" * 2000
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["bak1"],
            text_excerpt="avatar",
            char_offset=100,
            start_sentence_index=0,
            end_sentence_index=0,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="bak1",
                    avatar="baerenklau",
                    video_clip_id="bak1_clip",
                    projector="rz21",
                )
            ],
        )
    ]
    points = __import__("asyncio").run(
        Teil2AtmosphereScheduler().schedule(
            script_text=script,
            sentences=["Satz."],
            segments=segments,
            gesamtkonzept=Gesamtkonzept(anarchy_curve=AnarchyCurve(start=0.4, end=0.8)),
            dramaturgy=DramaturgyDecision(
                reason="test", tags=[], mood="tension", intensity=0.5, cue_points=[]
            ),
            avatar_clip_ids={"bak1_clip"},
        )
    )
    total = estimate_script_duration_sec(script, segments)
    min_each = min_recurring_appearances(total)
    assert count_atmosphere_clip(points, "bonnie") >= min_each
    assert count_atmosphere_clip(points, "clyde") >= min_each
    windows = build_avatar_windows(script, segments, total)
    if not windows:
        return
    start, end = windows[0].start_sec, windows[0].end_sec
    for point in points:
        if start <= point.time_offset_sec < end and point.visual:
            assert point.visual.projector != "rz21"

