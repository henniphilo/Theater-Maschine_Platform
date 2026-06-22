import logging
from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, LightCue, OscCommand, VisualAction, resolve_light_scene_ids
from app.director.cues.cue_points import decision_from_cue_point, normalize_cue_points
from app.director.cues.visual_outputs import resolve_visual_assignments
from app.director.media.database import MediaDatabase
from app.director.outputs.eos_light import (
    eos_chan_level,
    eos_group_level,
    eos_key_out,
    expand_channels,
    parse_eos_chan_command,
    EOS_GROUP_ADDRESS_RE,
)
from app.services.video_cue_catalog import get_video_cue_catalog_service

_osc_fail_logger = logging.getLogger("theatermaschine.osc")


def _light_osc_target(osc_host: str, osc_port: int) -> tuple[str, int]:
    if settings.light_output == "tcp":
        return settings.light_tcp_host, settings.light_tcp_port
    return osc_host, osc_port


def _resolve_light_intensity(light: LightCue, decision: DramaturgyDecision) -> float:
    if light.intensity is not None:
        return light.intensity
    return max(0.0, min(1.0, decision.intensity))


def _eos_commands_for_scene(
    scene_id: str,
    *,
    intensity: float = 1.0,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    light_host, light_port = _light_osc_target(osc_host, osc_port)
    scene = next((s for s in MediaDatabase().light_scenes if s.id == scene_id), None)
    commands: list[OscCommand] = []
    if scene is None:
        return commands
    for group in scene.groups:
        group_id = int(str(group).strip())
        address, args = eos_group_level(group_id, intensity)
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
    for channel in expand_channels(scene.channels):
        address, args = eos_chan_level(channel, intensity)
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


def _eos_commands_for_light_cue(
    light: LightCue,
    *,
    decision: DramaturgyDecision,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    scene_ids = resolve_light_scene_ids(light)
    if not scene_ids:
        return []

    commands: list[OscCommand] = []
    if light.replace_previous and light.action.value != "fade_blackout":
        commands.append(_eos_blackout_command(osc_host=osc_host, osc_port=osc_port, is_dry_run=is_dry_run))

    light_intensity = _resolve_light_intensity(light, decision)
    for scene_id in scene_ids:
        commands.extend(
            _eos_commands_for_scene(
                scene_id,
                intensity=light_intensity,
                osc_host=osc_host,
                osc_port=osc_port,
                is_dry_run=is_dry_run,
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


def _touchdesigner_visual_commands(
    visual,
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    commands: list[OscCommand] = []
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
    return commands


def _pixera_visual_commands(
    visual,
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    catalog = get_video_cue_catalog_service().load()
    if not catalog.clips:
        return []

    commands: list[OscCommand] = []
    for output_id, clip_id, action in resolve_visual_assignments(visual):
        if action in (VisualAction.RECORD_LIVE, VisualAction.PLAY_RECORDING):
            continue
        try:
            cue_name = get_video_cue_catalog_service().pixera_cue_name(
                output_id, clip_id, catalog
            )
        except KeyError:
            continue
        commands.append(
            OscCommand(
                bridge="pixera",
                host=osc_host,
                port=osc_port,
                address=catalog.osc_address,
                args=[cue_name],
                dry_run=is_dry_run,
            )
        )
    return commands


def _visual_commands(
    visual,
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    mode = settings.visual_output
    commands: list[OscCommand] = []
    if mode in ("pixera", "both"):
        pixera_host = settings.pixera_osc_host or osc_host
        pixera_port = settings.pixera_osc_port or osc_port
        commands.extend(
            _pixera_visual_commands(
                visual,
                osc_host=pixera_host,
                osc_port=pixera_port,
                is_dry_run=is_dry_run,
            )
        )
    if mode in ("touchdesigner", "both"):
        commands.extend(
            _touchdesigner_visual_commands(
                visual,
                osc_host=osc_host,
                osc_port=osc_port,
                is_dry_run=is_dry_run,
            )
        )
    return commands


def _commands_for_single_decision(
    decision: DramaturgyDecision,
    *,
    osc_host: str,
    osc_port: int,
    is_dry_run: bool,
) -> list[OscCommand]:
    commands: list[OscCommand] = []

    if decision.visual:
        commands.extend(
            _visual_commands(
                decision.visual,
                osc_host=osc_host,
                osc_port=osc_port,
                is_dry_run=is_dry_run,
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

    if decision.light and resolve_light_scene_ids(decision.light):
        light = decision.light
        fade = light.fade_time
        scene_ids = resolve_light_scene_ids(light)

        if light.action.value == "fade_blackout":
            commands.append(_eos_blackout_command(osc_host=osc_host, osc_port=osc_port, is_dry_run=is_dry_run))
            if settings.light_osc_mirror:
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
                _eos_commands_for_light_cue(
                    light,
                    decision=decision,
                    osc_host=osc_host,
                    osc_port=osc_port,
                    is_dry_run=is_dry_run,
                )
            )
            if settings.light_osc_mirror:
                commands.append(
                    OscCommand(
                        bridge="light",
                        host=osc_host,
                        port=osc_port,
                        address="/light/set_scene",
                        args=[",".join(scene_ids), fade],
                        dry_run=is_dry_run,
                        mirror=True,
                    )
                )
    elif decision.light and decision.light.action.value == "fade_blackout":
        commands.append(_eos_blackout_command(osc_host=osc_host, osc_port=osc_port, is_dry_run=is_dry_run))
        if settings.light_osc_mirror:
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
    pixera = bridges.get("pixera")
    sound = bridges["sound"]
    lighting = bridges["lighting"]

    for cmd in commands:
        if cmd.bridge == "pixera" and pixera is not None:
            if cmd.address == "/pixera/args/cue/apply" and cmd.args:
                pixera.apply_cue(str(cmd.args[0]))
            sent.append(cmd)
            continue
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

            try:
                if cmd.mirror:
                    sent.append(cmd)
                    continue
                if cmd.address == "/eos/key/out":
                    lighting.blackout_signal(dry_run=cmd.dry_run)
                elif cmd.address.startswith("/eos/group/"):
                    match = EOS_GROUP_ADDRESS_RE.match(cmd.address)
                    if match is not None:
                        group = int(match.group(1))
                        kind = match.group(2)
                        intensity = float(cmd.args[0]) / 100.0 if kind == "level" and cmd.args else 1.0
                        lighting.apply_group(group, intensity=intensity, dry_run=cmd.dry_run)
                elif cmd.address.startswith("/eos/chan/"):
                    parsed = parse_eos_chan_command(cmd.address, cmd.args)
                    if parsed is not None:
                        channel, intensity = parsed
                        lighting.apply_channel(channel, intensity=intensity, dry_run=cmd.dry_run)
                elif cmd.address == "/light/blackout":
                    lighting.blackout(dry_run=cmd.dry_run)
                elif cmd.address == "/light/set_scene" and len(cmd.args) >= 2:
                    scene_arg = str(cmd.args[0])
                    scene_ids = [part.strip() for part in scene_arg.split(",") if part.strip()]
                    lighting.execute(
                        LightCue(
                            scene_ids=scene_ids if len(scene_ids) > 1 else [],
                            scene_id=scene_ids[0] if len(scene_ids) == 1 else None,
                            fade_time=float(cmd.args[1]),
                        ),
                        dry_run=cmd.dry_run,
                    )
            except Exception as exc:
                _osc_fail_logger.warning("[LIGHT FAILED] %s %s: %s", cmd.address, cmd.args, exc)
                continue
        sent.append(cmd)
    return sent
