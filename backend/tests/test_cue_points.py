from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.director.cues.cue_points import normalize_cue_points
from app.director.media.database import MediaDatabase
from app.director.outputs.eos_light import expand_channels
from app.director.outputs.osc_commands import build_osc_commands

_SCENE_A = "blendung_zuschauerraum"
_SCENE_B = "teppich_rot"
_SCENE_PARTIAL = "blendung_zuschauerraum"


def _light_osc_counts(scene_id: str, intensity: float) -> tuple[int, int, int]:
    scene = next(s for s in MediaDatabase().light_scenes if s.id == scene_id)
    channels = len(scene.groups) + len(expand_channels(scene.channels))
    # Each scene activation sends /eos/key/out before channel levels.
    total = channels + 1
    if intensity >= 1.0:
        return total, channels, 0
    return total, 0, channels


def test_normalize_legacy_decision_to_cue_points() -> None:
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
        sound=SoundCue(cue_id="maschinen_grundader"),
        light=LightCue(scene_id=_SCENE_PARTIAL),
        reason="test",
    )
    points = normalize_cue_points(decision)
    assert len(points) == 1
    assert points[0].trigger == CuePointTrigger.START
    assert points[0].visual is not None


def test_build_osc_commands_from_multiple_cue_points() -> None:
    decision = DramaturgyDecision(
        reason="multi",
        intensity=1.0,
        cue_points=[
            CuePoint(
                trigger="start",
                intensity=1.0,
                visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
                sound=SoundCue(cue_id="maschinen_grundader"),
                light=LightCue(scene_id=_SCENE_A),
            ),
            CuePoint(
                trigger="keyword",
                keyword="Schuld",
                intensity=0.5,
                visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="fuchs"),
                sound=SoundCue(cue_id="dummy_stinger"),
                light=LightCue(scene_id=_SCENE_B),
            ),
        ],
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    expected_total, expected_full, expected_at = _light_osc_counts(_SCENE_A, 1.0)
    total_b, _, at_b = _light_osc_counts(_SCENE_B, 0.5)
    assert len(light_cmds) == expected_total + total_b
    full_cmds = [c for c in light_cmds if c.address.endswith("/full")]
    at_cmds = [c for c in light_cmds if c.address.endswith("/at")]
    assert len(full_cmds) == expected_full
    assert len(at_cmds) == at_b
    if at_cmds:
        assert at_cmds[0].args == [50.0]


def test_build_osc_commands_light_explicit_intensity() -> None:
    decision = DramaturgyDecision(
        reason="dezent",
        intensity=1.0,
        light=LightCue(scene_id=_SCENE_PARTIAL, intensity=0.4),
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert light_cmds
    key_outs = [c for c in light_cmds if c.address.endswith("/key/out")]
    at_cmds = [c for c in light_cmds if c.address.endswith("/at")]
    assert len(key_outs) == 1
    assert at_cmds
    assert all(c.args == [40.0] for c in at_cmds)
