"""Lighting: TCP 1.0 EOS session on port 3032 — connect, then EOS OSC on same socket."""

from pythonosc import udp_client

from app.core.config import settings
from app.director.cues.cue_models import LightCue, resolve_light_scene_ids
from app.director.media.database import MediaDatabase
from app.director.outputs.eos_light import eos_chan_level, eos_group_level, expand_channels
from app.director.outputs.light_scene_tracker import (
    clear_active_light_scenes,
    fade_out_scene,
    replace_active_light_scenes,
)
from app.director.outputs.light_tcp import (
    LightDeskConnectionError,
    close_light_tcp,
    get_light_tcp_session,
    log_light_failure,
)
from app.director.outputs.osc_log import log_osc_command


class LightingBridge:
    def __init__(
        self,
        media_db: MediaDatabase | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.host = host or settings.light_tcp_host
        self.port = port or settings.light_tcp_port
        self._desk_osc_client: udp_client.SimpleUDPClient | None = None
        self._preview_osc_client: udp_client.SimpleUDPClient | None = None
        if settings.light_output == "osc":
            self._desk_osc_client = udp_client.SimpleUDPClient(
                settings.light_desk_host(),
                settings.light_desk_port(),
            )
        if settings.light_output == "mirror" or settings.light_osc_mirror:
            self._preview_osc_client = udp_client.SimpleUDPClient(
                settings.osc_host,
                settings.osc_port,
            )

    def execute(self, cue: LightCue, dry_run: bool = False) -> None:
        if cue.action.value == "fade_blackout" or (
            not resolve_light_scene_ids(cue) and cue.scene_id in (None, "blackout")
        ):
            self.blackout(dry_run=dry_run)
            return

        if settings.light_output == "tcp" and not self._open_tcp_session(dry_run=dry_run):
            return

        self.send_scene(cue, dry_run=dry_run)

    def connect_desk(self, dry_run: bool = False) -> None:
        if settings.light_output == "tcp":
            self._open_tcp_session(dry_run=dry_run)

    def disconnect_desk(self, dry_run: bool = False) -> None:
        if settings.light_output == "tcp":
            get_light_tcp_session().close_session(dry_run=dry_run)
            close_light_tcp()

    def send_scene(self, cue: LightCue, dry_run: bool = False) -> None:
        if cue.action.value == "fade_blackout" or not resolve_light_scene_ids(cue):
            self.blackout_signal(dry_run=dry_run)
            return

        scene_ids = resolve_light_scene_ids(cue)
        primary = next((s for s in self.media_db.light_scenes if s.id == scene_ids[0]), None)
        fade = cue.fade_time if cue.fade_time else (primary.fade_time if primary else 4.0)

        if settings.light_output == "mirror":
            self._apply_mirror_scene(cue, scene_ids=scene_ids, fade=fade, dry_run=dry_run)
            return

        if settings.light_output == "tcp" and not get_light_tcp_session().connected:
            if not dry_run:
                if not self._open_tcp_session(dry_run=dry_run):
                    if settings.light_osc_mirror:
                        self._send_preview_osc(
                            "/light/set_scene",
                            ",".join(scene_ids),
                            fade,
                            dry_run=dry_run,
                        )
                    return

        if cue.replace_previous:
            previous = replace_active_light_scenes(scene_ids)
            self._fade_out_scenes(previous, dry_run=dry_run)
        else:
            replace_active_light_scenes(scene_ids)

        intensity = cue.intensity if cue.intensity is not None else 1.0
        if intensity <= 0.0:
            self._fade_out_scenes(scene_ids, dry_run=dry_run)
            return

        for scene_id in scene_ids:
            scene = next((s for s in self.media_db.light_scenes if s.id == scene_id), None)
            if scene is None:
                continue
            self._apply_scene_channels(
                scene.channels,
                groups=scene.groups,
                intensity=intensity,
                dry_run=dry_run,
            )

        if settings.light_osc_mirror:
            self._send_preview_osc("/light/set_scene", ",".join(scene_ids), fade, dry_run=dry_run)

    def blackout_signal(self, dry_run: bool = False) -> None:
        previous = clear_active_light_scenes()
        if settings.light_output == "mirror":
            for scene_id in previous:
                fade_out_scene(scene_id)
        else:
            self._fade_out_scenes(previous, dry_run=dry_run)

        if settings.light_output == "mirror" or settings.light_osc_mirror:
            self._send_preview_osc("/light/blackout", dry_run=dry_run)

    def _apply_mirror_scene(
        self,
        cue: LightCue,
        *,
        scene_ids: list[str],
        fade: float,
        dry_run: bool,
    ) -> None:
        if cue.replace_previous:
            previous = replace_active_light_scenes(scene_ids)
            for scene_id in previous:
                fade_out_scene(scene_id)
        else:
            replace_active_light_scenes(scene_ids)

        intensity = cue.intensity if cue.intensity is not None else 1.0
        if intensity <= 0.0:
            for scene_id in scene_ids:
                fade_out_scene(scene_id)
            self._send_preview_osc("/light/blackout", dry_run=dry_run)
            return

        self._send_preview_osc("/light/set_scene", ",".join(scene_ids), fade, dry_run=dry_run)

    def _fade_out_scenes(self, scene_ids: list[str], *, dry_run: bool = False) -> None:
        for scene_id in scene_ids:
            scene = next((s for s in self.media_db.light_scenes if s.id == scene_id), None)
            if scene is None:
                continue
            self._apply_scene_channels(
                scene.channels,
                groups=scene.groups,
                intensity=0.0,
                dry_run=dry_run,
            )
            fade_out_scene(scene_id)

    def blackout(self, dry_run: bool = False) -> None:
        self.blackout_signal(dry_run=dry_run)
        if settings.light_output == "tcp":
            get_light_tcp_session().close_session(dry_run=dry_run)
            close_light_tcp()

    def hold(self, cue: LightCue, dry_run: bool = False) -> None:
        self.send_scene(cue, dry_run=dry_run)

    def _apply_scene_channels(
        self,
        channel_specs: list[str],
        *,
        groups: list[str] | None = None,
        intensity: float = 1.0,
        dry_run: bool,
    ) -> None:
        for group in groups or []:
            address, args = eos_group_level(int(group), intensity)
            self._send_desk_osc(address, *args, dry_run=dry_run)
        for channel in expand_channels(channel_specs):
            address, args = eos_chan_level(channel, intensity)
            self._send_desk_osc(address, *args, dry_run=dry_run)

    def apply_group(self, group: int, *, intensity: float = 1.0, dry_run: bool = False) -> None:
        if settings.light_output == "mirror":
            return
        if settings.light_output == "tcp" and not self._open_tcp_session(dry_run=dry_run):
            return
        address, args = eos_group_level(group, intensity)
        self._send_desk_osc(address, *args, dry_run=dry_run)

    def apply_channel(self, channel: int, *, intensity: float = 1.0, dry_run: bool = False) -> None:
        if settings.light_output == "mirror":
            return
        if settings.light_output == "tcp" and not self._open_tcp_session(dry_run=dry_run):
            return
        address, args = eos_chan_level(channel, intensity)
        self._send_desk_osc(address, *args, dry_run=dry_run)

    def _open_tcp_session(self, *, dry_run: bool) -> bool:
        try:
            get_light_tcp_session().open_session(dry_run=dry_run)
            return True
        except LightDeskConnectionError as exc:
            log_light_failure(str(exc))
            return False

    def _desk_osc_target(self) -> tuple[str, int]:
        return settings.light_desk_host(), settings.light_desk_port()

    def _send_desk_osc(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        if settings.light_output == "tcp":
            try:
                get_light_tcp_session().send_osc(address, list(args), dry_run=is_dry_run)
            except (LightDeskConnectionError, RuntimeError, OSError) as exc:
                log_light_failure(f"{address}: {exc}")
            return
        host, port = self._desk_osc_target()
        log_osc_command(
            host,
            port,
            address,
            list(args),
            dry_run=is_dry_run,
            bridge="light",
        )
        if is_dry_run or self._desk_osc_client is None:
            return
        self._desk_osc_client.send_message(address, list(args))

    def _send_preview_osc(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        log_osc_command(
            settings.osc_host,
            settings.osc_port,
            address,
            list(args),
            dry_run=is_dry_run,
            bridge="light",
        )
        if is_dry_run or self._preview_osc_client is None:
            return
        self._preview_osc_client.send_message(address, list(args))
