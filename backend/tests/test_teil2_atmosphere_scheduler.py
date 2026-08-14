"""Tests for Teil-2 atmosphere scheduler."""

from app.director.cues.cue_models import CuePointTrigger, DramaturgyDecision, VisualOutputAssignment
from app.schemas.inszenierung import AnarchyCurve, AvatarSpeechLayer, AvatarTextSegment
from app.services.teil2_atmosphere_scheduler import (
    atmosphere_fill_count,
    build_avatar_windows,
    estimate_script_duration_sec,
    free_projectors_at,
    reserved_projectors_at,
)


def test_free_projectors_excludes_avatar_beamer() -> None:
    script = "A" * 1000
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["bak1"],
            text_excerpt="test",
            char_offset=100,
            start_sentence_index=1,
            end_sentence_index=1,
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
    total = estimate_script_duration_sec(script, segments)
    windows = build_avatar_windows(script, segments, total)
    assert windows
    mid = (windows[0].start_sec + windows[0].end_sec) / 2
    reserved = reserved_projectors_at(windows, mid)
    assert "rz21" in reserved
    free = free_projectors_at(windows, mid)
    assert "rz21" not in free
    assert "adam" in free or "eva" in free


def test_atmosphere_fill_count_escalates_with_anarchy() -> None:
    # Adam/Eva always, plus one extra free beamer even early.
    assert atmosphere_fill_count(3, 0.1) == 3
    assert atmosphere_fill_count(3, 0.4) == 3
    assert atmosphere_fill_count(3, 0.7) == 3
    assert atmosphere_fill_count(1, 0.1) == 1
    assert atmosphere_fill_count(0, 0.9) == 0


def test_rule_fallback_always_covers_adam_eva_when_free(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    from app.services.teil2_atmosphere_scheduler import Teil2AtmosphereScheduler

    script = "A" * 1500
    # Avatar only on rz21 — Adam/Eva must get atmosphere even at low anarchy.
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
                    outputs=[VisualOutputAssignment(output_id="rz21", clip_id="bak1_clip")],
                )
            ],
        )
    ]
    scheduler = Teil2AtmosphereScheduler()
    points = __import__("asyncio").run(
        scheduler.schedule(
            script_text=script,
            sentences=["Satz."],
            segments=segments,
            gesamtkonzept=__import__(
                "app.schemas.inszenierung", fromlist=["Gesamtkonzept"]
            ).Gesamtkonzept(anarchy_curve=AnarchyCurve(start=0.05, end=0.2)),
            dramaturgy=DramaturgyDecision(
                reason="test", tags=[], mood="calm", intensity=0.2, cue_points=[]
            ),
            avatar_clip_ids={"bak1_clip"},
        )
    )
    assert points
    projectors = {
        p.visual.projector
        for p in points
        if p.visual is not None and p.visual.projector
    }
    assert "adam" in projectors
    assert "eva" in projectors
    total = estimate_script_duration_sec(script, segments)
    windows = build_avatar_windows(script, segments, total)
    assert windows
    for point in points:
        if (
            windows[0].start_sec <= point.time_offset_sec < windows[0].end_sec
            and point.visual
        ):
            assert point.visual.projector != "rz21"


def test_rule_fallback_produces_time_cues(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    from app.services.teil2_atmosphere_scheduler import Teil2AtmosphereScheduler

    script = "Erster Satz. Zweiter Satz. Dritter Satz."
    segments: list[AvatarTextSegment] = []
    dramaturgy = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.5,
        cue_points=[],
    )
    scheduler = Teil2AtmosphereScheduler()
    points = __import__("asyncio").run(
        scheduler.schedule(
            script_text=script,
            sentences=["Erster Satz.", "Zweiter Satz.", "Dritter Satz."],
            segments=segments,
            gesamtkonzept=__import__(
                "app.schemas.inszenierung", fromlist=["Gesamtkonzept"]
            ).Gesamtkonzept(anarchy_curve=AnarchyCurve(start=0.4, end=0.9)),
            dramaturgy=dramaturgy,
            avatar_clip_ids=set(),
        )
    )
    assert points
    assert all(p.trigger == CuePointTrigger.TIME for p in points)
    assert all(p.visual and p.visual.clip_id for p in points)
    assert all(p.visual.clip_id not in {"random", "avatar2"} for p in points)


def test_atmosphere_starts_immediately_and_is_dense_early(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    from app.services.teil2_atmosphere_scheduler import Teil2AtmosphereScheduler

    script = "A" * 2000
    points = __import__("asyncio").run(
        Teil2AtmosphereScheduler().schedule(
            script_text=script,
            sentences=["Satz."],
            segments=[],
            gesamtkonzept=__import__(
                "app.schemas.inszenierung", fromlist=["Gesamtkonzept"]
            ).Gesamtkonzept(anarchy_curve=AnarchyCurve(start=0.2, end=0.4)),
            dramaturgy=DramaturgyDecision(
                reason="test", tags=[], mood="calm", intensity=0.3, cue_points=[]
            ),
            avatar_clip_ids=set(),
        )
    )
    times = sorted({p.time_offset_sec for p in points})
    assert times
    assert times[0] <= 0.5
    early = [t for t in times if t <= 30.0]
    assert len(early) >= 4


def test_rule_fills_multiple_free_projectors_beside_avatar(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    from app.services.teil2_atmosphere_scheduler import Teil2AtmosphereScheduler

    script = "A" * 2000
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["bak1"],
            text_excerpt="avatar",
            char_offset=200,
            start_sentence_index=0,
            end_sentence_index=0,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="bak1",
                    avatar="baerenklau",
                    video_clip_id="bak1_clip",
                    projector="rz21",
                    outputs=[VisualOutputAssignment(output_id="rz21", clip_id="bak1_clip")],
                )
            ],
        )
    ]
    scheduler = Teil2AtmosphereScheduler()
    points = __import__("asyncio").run(
        scheduler.schedule(
            script_text=script,
            sentences=["Satz eins.", "Satz zwei.", "Satz drei."],
            segments=segments,
            gesamtkonzept=__import__(
                "app.schemas.inszenierung", fromlist=["Gesamtkonzept"]
            ).Gesamtkonzept(anarchy_curve=AnarchyCurve(start=0.6, end=0.95)),
            dramaturgy=DramaturgyDecision(
                reason="test", tags=[], mood="tension", intensity=0.7, cue_points=[]
            ),
            avatar_clip_ids={"bak1_clip"},
        )
    )
    assert len(points) >= 3
    total = estimate_script_duration_sec(script, segments)
    windows = build_avatar_windows(script, segments, total)
    assert windows
    avatar_mid = (windows[0].start_sec + windows[0].end_sec) / 2

    by_time: dict[float, set[str]] = {}
    for point in points:
        assert point.visual is not None
        projector = point.visual.projector
        assert projector is not None
        by_time.setdefault(point.time_offset_sec, set()).add(projector)
        # While the avatar owns rz21, Begleitvideo must stay off that beamer.
        if windows[0].start_sec <= point.time_offset_sec < windows[0].end_sec:
            assert projector != "rz21"

    assert max(len(projs) for projs in by_time.values()) >= 2
    # Prefer at least one multi-beamer tick near the avatar window.
    near_avatar = [
        projs
        for t, projs in by_time.items()
        if abs(t - avatar_mid) < 30.0
    ]
    assert near_avatar
    assert max(len(projs) for projs in near_avatar) >= 2
