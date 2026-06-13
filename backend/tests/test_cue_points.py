from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.director.cues.cue_points import decision_from_cue_point, min_cue_points_for_text, normalize_cue_points
from app.director.outputs.osc_commands import build_osc_commands


def test_normalize_legacy_decision_to_cue_points() -> None:
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="kuh"),
        sound=SoundCue(cue_id="dummy_drone"),
        light=LightCue(scene_id="vorbuehnenzug"),
        reason="test",
    )
    points = normalize_cue_points(decision)
    assert len(points) == 1
    assert points[0].trigger == CuePointTrigger.START
    assert points[0].visual is not None


def test_build_osc_commands_from_multiple_cue_points() -> None:
    decision = DramaturgyDecision(
        reason="multi",
        cue_points=[
            CuePoint(
                trigger="start",
                visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="kuh"),
                sound=SoundCue(cue_id="dummy_drone"),
                light=LightCue(scene_id="vorbuehnenzug"),
            ),
            CuePoint(
                trigger="keyword",
                keyword="Schuld",
                visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="fuchs"),
                sound=SoundCue(cue_id="dummy_stinger"),
                light=LightCue(scene_id="cyc_fluter"),
            ),
        ],
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert len(light_cmds) == 10
    assert all(c.address.endswith("/full") for c in light_cmds)
    assert all(c.args == [] for c in light_cmds)


def test_min_cue_points_scales_with_text_length() -> None:
    assert min_cue_points_for_text("kurz") == 1
    assert min_cue_points_for_text("x" * 600) >= 2
    assert min_cue_points_for_text("x" * 1500) >= 4


def test_decision_from_cue_point() -> None:
    base = DramaturgyDecision(reason="basis", mood="neutral", intensity=0.5)
    point = CuePoint(trigger="start", function="entlarven", visual=VisualCue(clip_id="ente"))
    mini = decision_from_cue_point(base, point)
    assert mini.visual is not None
    assert mini.visual.clip_id == "ente"
    assert "entlarven" in mini.reason
