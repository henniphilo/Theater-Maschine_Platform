"""Tests for Teil-2 atmosphere cue injection."""

from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision
from app.schemas.inszenierung import AnarchyCurve, AvatarSpeechLayer, AvatarTextSegment, Gesamtkonzept
from app.services.teil2_atmosphere_cues import inject_atmosphere_visuals


def test_inject_atmosphere_adds_visual_on_side_beamer() -> None:
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["bak1"],
            text_excerpt="test",
            char_offset=0,
            start_sentence_index=1,
            end_sentence_index=1,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="bak1",
                    avatar="baerenklau",
                    video_clip_id="bak1_nicolaspflanzen3",
                    projector="rz21",
                )
            ],
        )
    ]
    decision = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.6,
        cue_points=[
            CuePoint(
                trigger=CuePointTrigger.SENTENCE_END,
                sentence_index=1,
                function="verstärken",
                intensity=0.6,
            )
        ],
    )
    curve = AnarchyCurve(start=0.35, end=0.9)
    injected = inject_atmosphere_visuals(
        decision,
        sentences=["a", "b", "c"],
        segments=segments,
        curve=curve,
        avatar_clip_ids={"bak1_nicolaspflanzen3"},
    )
    visual = injected.cue_points[0].visual
    assert visual is not None
    assert visual.video_type == "atmosphere"
    assert visual.projector in {"adam", "eva", "led"}
    assert visual.projector != "rz21"


def test_inject_atmosphere_strips_top_level_avatar_visual() -> None:
    decision = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.6,
        visual={"clip_id": "bak3_hasen", "video_type": "atmosphere"},
        cue_points=[],
    )
    injected = inject_atmosphere_visuals(
        decision,
        sentences=["x"],
        segments=[],
        curve=AnarchyCurve(start=0.35, end=0.9),
        avatar_clip_ids={"bak3_hasen"},
    )
    assert injected.visual is None
