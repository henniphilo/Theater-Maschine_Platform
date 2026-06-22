from app.director.cues.cue_models import DramaturgyDecision, LightCue
from app.director.outputs.eos_light import eos_group_level
from app.director.outputs.osc_commands import build_osc_commands


def test_light_scene_replaces_previous_with_key_out() -> None:
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
    assert light_cmds[0].address == "/eos/key/out"
    assert any(c.address == "/eos/chan/46/full" for c in light_cmds)


def test_combined_light_scenes_share_one_key_out() -> None:
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
    key_outs = [c for c in light_cmds if c.address == "/eos/key/out"]
    assert len(key_outs) == 1
    addresses = {c.address for c in light_cmds}
    assert "/eos/chan/46/at" in addresses
    assert "/eos/chan/6/at" in addresses
    assert "/eos/chan/10/at" in addresses


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
    assert address == "/eos/group/2/level"
    assert args == [50.0]
