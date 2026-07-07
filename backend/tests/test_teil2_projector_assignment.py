"""Tests for Teil-2 projector assignment."""

from app.director.cues.cue_models import VisualOutputAssignment
from app.schemas.inszenierung import AvatarSpeechLayer
from app.services.teil2_dramaturgy_routing import route_dramaturgy_away_from_projectors
from app.services.teil2_projector_assignment import (
    ALL_PROJECTORS,
    assign_projectors_for_layers,
    build_avatar_visual_cue,
    pick_atmosphere_projectors,
    pick_distinct_projector,
    projector_mode_for_anarchy,
)
from app.director.cues.cue_models import CuePoint, DramaturgyDecision, VisualCue


def test_projector_mode_switches_at_half_anarchy():
    assert projector_mode_for_anarchy(0.4) == "single"
    assert projector_mode_for_anarchy(0.5) == "all"


def test_chorus_gets_distinct_projectors():
    layers = [
        AvatarSpeechLayer(avatar_speech_id="DEL1", avatar="delphin", video_clip_id="avatar"),
        AvatarSpeechLayer(avatar_speech_id="LG1", avatar="lamm", video_clip_id="esel"),
    ]
    assigned = assign_projectors_for_layers(layers, anarchy_level=0.2)
    projectors = {layer.projector for layer in assigned}
    assert len(projectors) == 2
    assert all(len(layer.outputs) == 1 for layer in assigned)


def test_chorus_high_anarchy_still_uses_distinct_single_beamers():
    layers = [
        AvatarSpeechLayer(avatar_speech_id="BK1", avatar="baerenklau", video_clip_id="bk1_caro"),
        AvatarSpeechLayer(avatar_speech_id="BK2", avatar="baerenklau", video_clip_id="bk1_caroline"),
        AvatarSpeechLayer(avatar_speech_id="BK3", avatar="baerenklau", video_clip_id="bk1_thomas"),
    ]
    assigned = assign_projectors_for_layers(layers, anarchy_level=0.85)
    projectors = [layer.projector for layer in assigned]
    assert len(set(projectors)) == 3
    assert all(len(layer.outputs) == 1 for layer in assigned)


def test_sequential_segments_rotate_projectors_with_shared_used_set():
    layers_a = [AvatarSpeechLayer(avatar_speech_id="t1", avatar="delphin", video_clip_id="thiemo")]
    layers_b = [AvatarSpeechLayer(avatar_speech_id="b1", avatar="delphin", video_clip_id="branko")]
    used: set[str] = set()
    assigned_a = assign_projectors_for_layers(layers_a, anarchy_level=0.2, used=used)
    assigned_b = assign_projectors_for_layers(layers_b, anarchy_level=0.2, used=used)
    assert assigned_a[0].projector != assigned_b[0].projector


def test_avatar_visual_cue_uses_layer_blend_when_anarchic():
    layer = AvatarSpeechLayer(
        avatar_speech_id="BK1",
        avatar="baerenklau",
        video_clip_id="avatar2",
        projector="rz21",
        outputs=[VisualOutputAssignment(output_id="rz21", clip_id="avatar2")],
    )
    cue = build_avatar_visual_cue(layer, anarchy_level=0.6, duration_ms=5000)
    assert cue.blend_mode == "layer"
    assert cue.video_type == "avatar"
    assert len(cue.outputs) == 1


def test_atmosphere_avoids_all_avatar_beamers_when_one_free():
    reserved = {"rz21", "adam", "eva"}
    targets = pick_atmosphere_projectors(2, reserved=reserved, seed=0)
    assert targets == ["led", "led"]


def test_atmosphere_falls_back_to_rz21_overlay_when_all_reserved():
    reserved = set(ALL_PROJECTORS)
    targets = pick_atmosphere_projectors(1, reserved=reserved, seed=0)
    assert targets == ["rz21"]


def test_atmosphere_prefers_adam_eva_when_rz21_reserved():
    reserved = {"rz21"}
    targets = pick_atmosphere_projectors(2, reserved=reserved, seed=0)
    assert targets[0] == "adam"
    assert targets[1] == "eva"


def test_route_dramaturgy_strips_top_level_avatar_visual():
    decision = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.8,
        visual=VisualCue(clip_id="bak2_krabbe", video_type="atmosphere"),
    )
    routed = route_dramaturgy_away_from_projectors(
        decision,
        reserved_projectors={"rz21"},
        avatar_clip_ids={"bak2_krabbe"},
        seed=0,
    )
    assert routed.visual is None


def test_route_dramaturgy_puts_atmosphere_on_adam_when_rz21_reserved():
    decision = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.8,
        cue_points=[
            CuePoint(
                trigger="sentence_end",
                sentence_index=0,
                visual=VisualCue(clip_id="clyde"),
            )
        ],
    )
    routed = route_dramaturgy_away_from_projectors(
        decision,
        reserved_projectors={"rz21"},
        seed=0,
    )
    visual = routed.cue_points[0].visual
    assert visual is not None
    assert visual.projector == "adam"
    assert visual.outputs[0].output_id == "adam"


def test_pick_distinct_projector_skips_used_beamers():
    used = {"rz21", "adam"}
    assert pick_distinct_projector(preferred="rz21", used=used, fallback_index=0) == "eva"
