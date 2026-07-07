import re

from app.core.config import settings
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
    if intensity >= 1.0:
        return channels, channels, 0
    return channels, 0, channels


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


def _light_level_cmds(light_cmds: list) -> list:
    """Partial-intensity channel commands: /eos/chan/N with percent arg (not /full)."""
    return [
        c
        for c in light_cmds
        if re.fullmatch(r"/eos/chan/\d+", c.address) and c.args
    ]


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
    fade_out_a, _, _ = _light_osc_counts(_SCENE_A, 0.0)
    assert len(light_cmds) == expected_total + fade_out_a + total_b
    full_cmds = [c for c in light_cmds if c.address.endswith("/full")]
    assert len(full_cmds) == expected_full
    level_cmds = [c for c in _light_level_cmds(light_cmds) if c.args and c.args[0] > 0]
    assert len(level_cmds) == at_b
    if level_cmds:
        assert level_cmds[0].args == [50.0]


def test_build_osc_commands_light_explicit_intensity() -> None:
    decision = DramaturgyDecision(
        reason="dezent",
        intensity=1.0,
        light=LightCue(scene_id=_SCENE_PARTIAL, intensity=0.4),
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert light_cmds
    assert not any(c.address.endswith("/key/out") for c in light_cmds)
    level_cmds = _light_level_cmds(light_cmds)
    assert level_cmds
    assert all(c.args == [40.0] for c in level_cmds)


def test_light_osc_commands_use_desk_not_video_port() -> None:
    decision = DramaturgyDecision(
        reason="routing",
        intensity=1.0,
        light=LightCue(scene_id=_SCENE_PARTIAL),
    )
    commands = build_osc_commands(decision, dry_run=True, host="127.0.0.1", port=7000)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert light_cmds
    assert all(c.host == settings.light_tcp_host for c in light_cmds)
    assert all(c.port == settings.light_tcp_port for c in light_cmds)
