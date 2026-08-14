from datetime import UTC, datetime, timedelta

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightCue,
    VisualCue,
    resolve_light_scene_ids,
)
from app.director.cues.projector_state import ProjectorState
from app.director.outputs.light_scene_tracker import reset_light_scene_tracker
from app.director.pipeline import DirectorPipeline
from app.schemas.inszenierung import AvatarSpeechLayer, AvatarTextSegment
from app.services.avatar_required_lights import (
    apply_avatar_required_lights,
    apply_required_lights_to_plan,
    required_light_scenes_for_clip,
)


def test_required_scenes_match_pixera_and_catalog_ids() -> None:
    assert required_light_scenes_for_clip("SCH4_Thomas") == ("klaviertasten",)
    assert required_light_scenes_for_clip("sch4_thomas") == ("klaviertasten",)
    assert required_light_scenes_for_clip("KI_RZ21.WO2_Branko") == ("klaviertasten",)
    assert required_light_scenes_for_clip("bk1_caro") == ()


def test_avatar_execute_attaches_klaviertasten() -> None:
    reset_light_scene_tracker()
    decision = DramaturgyDecision(
        reason="Avatar-Sprache",
        tags=["teil2", "avatar"],
        mood="tension",
        intensity=0.5,
        visual=VisualCue(
            clip_id="sch4_thomas",
            video_type="avatar",
            projector="adam",
            lock_until_finished=True,
        ),
    )
    updated = apply_avatar_required_lights(decision)
    assert updated.light is not None
    assert resolve_light_scene_ids(updated.light) == ["klaviertasten"]


def test_later_light_cue_keeps_klaviertasten_while_avatar_locked() -> None:
    now = datetime.now(UTC)
    projectors = ProjectorState()
    projectors.lock_after_play(
        VisualCue(
            clip_id="wo2_branko",
            video_type="avatar",
            projector="eva",
            lock_until_finished=True,
            duration_ms=8000,
        ),
        now=now,
    )
    decision = DramaturgyDecision(
        reason="Stichwort",
        tags=["teil2"],
        mood="anarchy",
        intensity=0.6,
        light=LightCue(scene_id="saallicht"),
    )
    updated = apply_avatar_required_lights(decision, projectors)
    assert resolve_light_scene_ids(updated.light) == ["saallicht", "klaviertasten"]


def test_blackout_is_not_overridden() -> None:
    projectors = ProjectorState()
    projectors.lock_after_play(
        VisualCue(
            clip_id="sch4_thomas",
            video_type="avatar",
            projector="rz21",
            lock_until_finished=True,
            duration_ms=8000,
        ),
        now=datetime.now(UTC),
    )
    decision = DramaturgyDecision(
        reason="Blackout",
        tags=["teil2"],
        mood="anarchy",
        intensity=0.9,
        light=LightCue(scene_id="blackout"),
    )
    updated = apply_avatar_required_lights(decision, projectors)
    assert resolve_light_scene_ids(updated.light) == ["blackout"]


def test_prepare_injects_light_when_no_overlapping_cue() -> None:
    decision = DramaturgyDecision(
        reason="Teil-2",
        tags=["teil2"],
        mood="anarchy",
        intensity=0.5,
        cue_points=[
            CuePoint(
                trigger=CuePointTrigger.KEYWORD,
                keyword="Geld",
                sentence_index=0,
                light=LightCue(scene_id="saallicht"),
            )
        ],
    )
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["sch4_thomas"],
            text_excerpt="Thomas am Klavier.",
            char_offset=10,
            start_sentence_index=2,
            end_sentence_index=2,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="sch4_thomas",
                    avatar="lamm",
                    video_clip_id="sch4_thomas",
                )
            ],
        )
    ]
    updated = apply_required_lights_to_plan(decision, segments)
    piano_points = [
        point
        for point in updated.cue_points
        if point.light and "klaviertasten" in resolve_light_scene_ids(point.light)
    ]
    assert piano_points
    assert piano_points[0].sentence_index == 2


def test_prepare_merges_into_overlapping_light_cue() -> None:
    decision = DramaturgyDecision(
        reason="Teil-2",
        tags=["teil2"],
        mood="anarchy",
        intensity=0.5,
        cue_points=[
            CuePoint(
                trigger=CuePointTrigger.KEYWORD,
                keyword="Klavier",
                sentence_index=4,
                light=LightCue(scene_id="musiker"),
            )
        ],
    )
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["wo2_branko"],
            text_excerpt="Branko.",
            start_sentence_index=4,
            end_sentence_index=4,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="wo2_branko",
                    avatar="wolf",
                    video_clip_id="WO2_Branko",
                )
            ],
        )
    ]
    updated = apply_required_lights_to_plan(decision, segments)
    assert resolve_light_scene_ids(updated.cue_points[0].light) == ["musiker", "klaviertasten"]


def test_execute_layered_emits_klaviertasten_with_avatar() -> None:
    reset_light_scene_tracker()
    pipeline = DirectorPipeline()
    decision = DramaturgyDecision(
        reason="Avatar-Sprache",
        tags=["teil2", "avatar"],
        mood="tension",
        intensity=0.5,
        visual=VisualCue(
            clip_id="sch4_thomas",
            video_type="avatar",
            projector="adam",
            lock_until_finished=True,
            duration_ms=4000,
        ),
        timestamp=0,
    )
    result = pipeline.execute_layered(decision, skip_interval_check=True)
    assert result.executed
    light_cmds = [cmd for cmd in result.planned_commands if cmd.bridge == "light" and not cmd.mirror]
    assert any(cmd.address.startswith("/eos/chan/26") for cmd in light_cmds)


def test_locked_avatar_does_not_apply_after_lock_expires() -> None:
    now = datetime.now(UTC)
    projectors = ProjectorState()
    projectors.lock_after_play(
        VisualCue(
            clip_id="sch4_thomas",
            video_type="avatar",
            projector="adam",
            lock_until_finished=True,
            duration_ms=1000,
        ),
        now=now,
    )
    later = now + timedelta(seconds=5)
    decision = DramaturgyDecision(
        reason="later",
        tags=["teil2"],
        mood="anarchy",
        intensity=0.4,
        light=LightCue(scene_id="saallicht"),
    )
    updated = apply_avatar_required_lights(decision, projectors, now=later)
    assert resolve_light_scene_ids(updated.light) == ["saallicht"]
