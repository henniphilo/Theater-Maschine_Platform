from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, OscCommand, VisualAction
from app.director.cues.cue_points import decision_from_cue_point, normalize_cue_points
from app.director.media.database import MediaDatabase
from app.director.outputs.eos_light import eos_chan_full, eos_key_out, expand_channels


def _light_osc_target(osc_host: str, osc_port: int) -> tuple[str, int]:
    if settings.light_output == "tcp":
        return settings.light_tcp_host, settings.light_tcp_port
    return osc_host, osc_port


def _eos_commands_for_scene(
    scene_id: str,
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    light_host, light_port = _light_osc_target(osc_host, osc_port)
    scene = next((s for s in MediaDatabase().light_scenes if s.id == scene_id), None)
    commands: list[OscCommand] = []
    for channel in expand_channels(scene.channels if scene else []):
        address, args = eos_chan_full(channel)
        commands.append(
            OscCommand(
                bridge="light",
                host=light_host,
                port=light_port,
                address=address,
                args=args,
                dry_run=is_dry_run,
            )
        )
    return commands


def _eos_blackout_command(
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> OscCommand:
    light_host, light_port = _light_osc_target(osc_host, osc_port)
    address, args = eos_key_out()
    return OscCommand(
        bridge="light",
        host=light_host,
        port=light_port,
        address=address,
        args=args,
        dry_run=is_dry_run,
    )


def _commands_for_single_decision(
    decision: DramaturgyDecision,
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    commands: list[OscCommand] = []

    if decision.visual:
        visual = decision.visual
        if visual.action == VisualAction.PLAY_CLIP and visual.clip_id:
            commands.append(
                OscCommand(
                    bridge="visual",
                    host=osc_host,
                    port=osc_port,
                    address="/visual/play_clip",
                    args=[visual.clip_id, visual.opacity, visual.fade_time],
                    dry_run=is_dry_run,
                )
            )
        elif visual.action == VisualAction.FADE_TO_BLACK:
            commands.append(
                OscCommand(
                    bridge="visual",
                    host=osc_host,
                    port=osc_port,
                    address="/visual/blackout",
                    args=[],
                    dry_run=is_dry_run,
                )
            )
        elif visual.action == VisualAction.STOP_CLIP:
            commands.append(
                OscCommand(
                    bridge="visual",
                    host=osc_host,
                    port=osc_port,
                    address="/visual/stop_clip",
                    args=[],
                    dry_run=is_dry_run,
                )
            )
        elif visual.action == VisualAction.RECORD_LIVE and visual.recording_id:
            commands.append(
                OscCommand(
                    bridge="visual",
                    host=osc_host,
                    port=osc_port,
                    address="/visual/record_start",
                    args=[visual.recording_id],
                    dry_run=is_dry_run,
                )
            )
        elif visual.action == VisualAction.PLAY_RECORDING and visual.recording_id:
            commands.append(
                OscCommand(
                    bridge="visual",
                    host=osc_host,
                    port=osc_port,
                    address="/visual/play_recording",
                    args=[visual.recording_id],
                    dry_run=is_dry_run,
                )
            )

    if decision.sound and decision.sound.cue_id:
        sound = decision.sound
        if sound.action.value == "trigger_cue":
            commands.append(
                OscCommand(
                    bridge="sound",
                    host=osc_host,
                    port=osc_port,
                    address="/sound/trigger",
                    args=[sound.cue_id, sound.volume],
                    dry_run=is_dry_run,
                )
            )
        elif sound.action.value == "stop_cue":
            commands.append(
                OscCommand(
                    bridge="sound",
                    host=osc_host,
                    port=osc_port,
                    address="/sound/stop",
                    args=[sound.cue_id],
                    dry_run=is_dry_run,
                )
            )
        elif sound.action.value == "set_volume":
            commands.append(
                OscCommand(
                    bridge="sound",
                    host=osc_host,
                    port=osc_port,
                    address="/sound/volume",
                    args=[sound.cue_id, sound.volume],
                    dry_run=is_dry_run,
                )
            )

    if decision.light and decision.light.scene_id:
        light = decision.light
        fade = light.fade_time

        if light.action.value == "fade_blackout":
            commands.append(_eos_blackout_command(osc_host=osc_host, osc_port=osc_port, is_dry_run=is_dry_run))
            if settings.light_output == "tcp" and settings.light_osc_mirror:
                commands.append(
                    OscCommand(
                        bridge="light",
                        host=osc_host,
                        port=osc_port,
                        address="/light/blackout",
                        args=[],
                        dry_run=is_dry_run,
                        mirror=True,
                    )
                )
        else:
            commands.extend(
                _eos_commands_for_scene(
                    light.scene_id,
                    osc_host=osc_host,
                    osc_port=osc_port,
                    is_dry_run=is_dry_run,
                )
            )
            if settings.light_output == "tcp" and settings.light_osc_mirror:
                commands.append(
                    OscCommand(
                        bridge="light",
                        host=osc_host,
                        port=osc_port,
                        address="/light/set_scene",
                        args=[light.scene_id, fade],
                        dry_run=is_dry_run,
                        mirror=True,
                    )
                )
    elif decision.light and decision.light.action.value == "fade_blackout":
        commands.append(_eos_blackout_command(osc_host=osc_host, osc_port=osc_port, is_dry_run=is_dry_run))
        if settings.light_output == "tcp" and settings.light_osc_mirror:
            commands.append(
                OscCommand(
                    bridge="light",
                    host=osc_host,
                    port=osc_port,
                    address="/light/blackout",
                    args=[],
                    dry_run=is_dry_run,
                    mirror=True,
                )
            )

    return commands


def build_osc_commands(
    decision: DramaturgyDecision,
    *,
    host: str | None = None,
    port: int | None = None,
    dry_run: bool | None = None,
) -> list[OscCommand]:
    osc_host = host or settings.osc_host
    osc_port = port or settings.osc_port
    is_dry_run = settings.osc_dry_run if dry_run is None else dry_run
    commands: list[OscCommand] = []

    points = normalize_cue_points(decision)
    if points:
        for point in points:
            mini = decision_from_cue_point(decision, point)
            commands.extend(
                _commands_for_single_decision(
                    mini,
                    osc_host=osc_host,
                    osc_port=osc_port,
                    is_dry_run=is_dry_run,
                )
            )
        return commands

    return _commands_for_single_decision(
        decision,
        osc_host=osc_host,
        osc_port=osc_port,
        is_dry_run=is_dry_run,
    )


def send_osc_commands(commands: list[OscCommand], bridges: dict[str, Any]) -> list[OscCommand]:
    """Send pre-built commands via bridges; returns list actually sent."""
    sent: list[OscCommand] = []
    touchdesigner = bridges["touchdesigner"]
    sound = bridges["sound"]
    lighting = bridges["lighting"]

    for cmd in commands:
        if cmd.bridge == "visual":
            if cmd.address == "/visual/play_clip" and len(cmd.args) >= 3:
                touchdesigner.play_clip(cmd.args[0], float(cmd.args[1]), float(cmd.args[2]))
            elif cmd.address == "/visual/blackout":
                touchdesigner.blackout()
            elif cmd.address == "/visual/stop_clip":
                touchdesigner.stop_clip()
            elif cmd.address == "/visual/record_start" and cmd.args:
                touchdesigner.start_recording(str(cmd.args[0]))
            elif cmd.address == "/visual/play_recording" and cmd.args:
                touchdesigner.play_recording(str(cmd.args[0]))
        elif cmd.bridge == "sound":
            from app.director.cues.cue_models import SoundAction, SoundCue

            if cmd.address == "/sound/trigger" and len(cmd.args) >= 2:
                sound.execute(
                    SoundCue(action=SoundAction.TRIGGER_CUE, cue_id=str(cmd.args[0]), volume=float(cmd.args[1])),
                    dry_run=cmd.dry_run,
                )
            elif cmd.address == "/sound/stop" and cmd.args:
                sound.execute(
                    SoundCue(action=SoundAction.STOP_CUE, cue_id=str(cmd.args[0])),
                    dry_run=cmd.dry_run,
                )
        elif cmd.bridge == "light":
            from app.director.cues.cue_models import LightCue

            if cmd.mirror:
                sent.append(cmd)
                continue
            if cmd.address == "/eos/key/out":
                lighting.blackout(dry_run=cmd.dry_run)
            elif cmd.address.startswith("/eos/chan/"):
                from app.director.outputs.eos_light import parse_eos_chan_address

                channel = parse_eos_chan_address(cmd.address)
                if channel is not None:
                    lighting.apply_channel(channel, dry_run=cmd.dry_run)
            elif cmd.address == "/light/blackout":
                lighting.blackout(dry_run=cmd.dry_run)
            elif cmd.address == "/light/set_scene" and len(cmd.args) >= 2:
                lighting.execute(
                    LightCue(scene_id=str(cmd.args[0]), fade_time=float(cmd.args[1])),
                    dry_run=cmd.dry_run,
                )
        sent.append(cmd)
    return sent
