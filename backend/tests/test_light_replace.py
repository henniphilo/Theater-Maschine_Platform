from app.director.cues.cue_models import DramaturgyDecision, LightCue
from app.director.outputs.eos_light import eos_group_level
from app.director.outputs.light_scene_tracker import reset_light_scene_tracker
from app.director.outputs.osc_commands import build_osc_commands


def setup_function() -> None:
    reset_light_scene_tracker()


def test_light_scene_replaces_previous_with_intensity_zero() -> None:
    decision = DramaturgyDecision(
        light=LightCue(scene_id="musiker", intensity=1.0),
        reason="test",
        tags=[],
        mood="neutral",
        intensity=0.5,
        timestamp=0.0,
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert not any(c.address.endswith("/key/out") for c in light_cmds)
    assert any(c.address == "/eos/chan/46/full" for c in light_cmds)

    decision2 = DramaturgyDecision(
        light=LightCue(scene_id="saallicht", intensity=0.8),
        reason="test",
        tags=[],
        mood="neutral",
        intensity=0.5,
        timestamp=1.0,
    )
    commands2 = build_osc_commands(decision2, dry_run=True)
    light_cmds2 = [c for c in commands2 if c.bridge == "light" and not c.mirror]
    zero_cmds = [c for c in light_cmds2 if c.address == "/eos/chan/46" and c.args == [0.0]]
    assert zero_cmds, "previous musiker channel should fade to 0"
    assert any(c.address == "/eos/group/2" and c.args == [80.0] for c in light_cmds2)


def test_combined_light_scenes_share_one_fade_out_pass() -> None:
    decision = DramaturgyDecision(
        light=LightCue(scene_ids=["musiker", "warme_buehnenflaeche"], intensity=0.8),
        reason="test",
        tags=[],
        mood="neutral",
        intensity=0.5,
        timestamp=0.0,
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert not any(c.address.endswith("/key/out") for c in light_cmds)
    addresses = {c.address for c in light_cmds}
    assert "/eos/chan/46" in addresses
    assert "/eos/chan/6" in addresses
    assert "/eos/chan/10" in addresses
    partial = [c for c in light_cmds if c.address == "/eos/chan/46"]
    assert partial and partial[0].args == [80.0]


def test_explicit_light_off_uses_intensity_zero() -> None:
    reset_light_scene_tracker()
    build_osc_commands(
        DramaturgyDecision(
            light=LightCue(scene_id="musiker", intensity=1.0),
            reason="on",
            tags=[],
            mood="neutral",
            intensity=0.5,
            timestamp=0.0,
        ),
        dry_run=True,
    )
    off = build_osc_commands(
        DramaturgyDecision(
            light=LightCue(scene_id="musiker", intensity=0.0, replace_previous=False),
            reason="off",
            tags=[],
            mood="neutral",
            intensity=0.0,
            timestamp=1.0,
        ),
        dry_run=True,
    )
    light_cmds = [c for c in off if c.bridge == "light" and not c.mirror]
    assert any(c.address == "/eos/chan/46" and c.args == [0.0] for c in light_cmds)


def test_group_scene_emits_eos_group_command() -> None:
    decision = DramaturgyDecision(
        light=LightCue(scene_id="saallicht", intensity=1.0),
        reason="test",
        tags=[],
        mood="neutral",
        intensity=0.5,
        timestamp=0.0,
    )
    commands = build_osc_commands(decision, dry_run=True)
    light_cmds = [c for c in commands if c.bridge == "light" and not c.mirror]
    assert any(c.address == "/eos/group/2/full" for c in light_cmds)


def test_eos_group_level_partial() -> None:
    address, args = eos_group_level(2, 0.5)
    assert address == "/eos/group/2"
    assert args == [50.0]
