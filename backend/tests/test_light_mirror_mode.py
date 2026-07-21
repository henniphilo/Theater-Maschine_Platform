from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, LightCue
from app.director.outputs.light_scene_tracker import reset_light_scene_tracker
from app.director.outputs.osc_commands import build_osc_commands


def test_build_osc_commands_mirror_mode_skips_eos(monkeypatch) -> None:
    reset_light_scene_tracker()
    monkeypatch.setattr(settings, "light_output", "mirror")
    monkeypatch.setattr(settings, "light_osc_mirror", False)
    monkeypatch.setattr(settings, "osc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "osc_port", 7000)
    monkeypatch.setattr(settings, "osc_dry_run", True)

    decision = DramaturgyDecision(
        light=LightCue(scene_id="saallicht", fade_time=4.0),
        reason="test",
    )
    commands = build_osc_commands(decision)

    assert len(commands) == 1
    assert commands[0].address == "/light/set_scene"
    assert commands[0].host == "127.0.0.1"
    assert commands[0].port == 7000
    assert commands[0].args == ["saallicht", 4.0]
    assert not any(cmd.address.startswith("/eos/") for cmd in commands)
