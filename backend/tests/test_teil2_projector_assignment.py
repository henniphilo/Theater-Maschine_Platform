"""Tests for Teil-2 projector assignment."""

from app.director.cues.cue_models import VisualOutputAssignment
from app.schemas.inszenierung import AvatarSpeechLayer
from app.services.teil2_projector_assignment import (
    ALL_PROJECTORS,
    assign_projectors_for_layers,
    build_avatar_visual_cue,
    projector_mode_for_anarchy,
)


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


def test_high_anarchy_projects_to_all_beamers():
    layers = [
        AvatarSpeechLayer(avatar_speech_id="WO1", avatar="wolf", video_clip_id="thiel"),
    ]
    assigned = assign_projectors_for_layers(layers, anarchy_level=0.7)
    assert len(assigned[0].outputs) == len(ALL_PROJECTORS)


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
