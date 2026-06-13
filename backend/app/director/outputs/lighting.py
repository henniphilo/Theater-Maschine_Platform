"""Lighting: TCP 1.0 EOS session on port 3032 — connect, then EOS OSC on same socket."""

from pythonosc import udp_client

from app.core.config import settings
from app.director.cues.cue_models import LightCue
from app.director.media.database import MediaDatabase
from app.director.outputs.eos_light import eos_chan_full, eos_key_out, expand_channels
from app.director.outputs.light_tcp import close_light_tcp, get_light_tcp_session
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
        self._td_osc_client: udp_client.SimpleUDPClient | None = None
        if settings.light_output == "osc":
            self._desk_osc_client = udp_client.SimpleUDPClient(settings.osc_host, settings.osc_port)
        if settings.light_osc_mirror:
            self._td_osc_client = udp_client.SimpleUDPClient(
                settings.osc_host,
                settings.osc_port,
            )

    def execute(self, cue: LightCue, dry_run: bool = False) -> None:
        if cue.scene_id is None or cue.scene_id == "blackout":
            self.blackout(dry_run=dry_run)
            return

        if settings.light_output == "tcp":
            get_light_tcp_session().open_session(dry_run=dry_run)

        self.send_scene(cue, dry_run=dry_run)

    def connect_desk(self, dry_run: bool = False) -> None:
        if settings.light_output == "tcp":
            get_light_tcp_session().open_session(dry_run=dry_run)

    def disconnect_desk(self, dry_run: bool = False) -> None:
        if settings.light_output == "tcp":
            get_light_tcp_session().close_session(dry_run=dry_run)
            close_light_tcp()

    def send_scene(self, cue: LightCue, dry_run: bool = False) -> None:
        if cue.scene_id is None or cue.scene_id == "blackout":
            self.blackout_signal(dry_run=dry_run)
            return
        scene = next((s for s in self.media_db.light_scenes if s.id == cue.scene_id), None)
        fade = cue.fade_time if cue.fade_time else (scene.fade_time if scene else 4.0)

        if settings.light_output == "tcp" and not get_light_tcp_session().connected:
            raise RuntimeError("Light desk TCP session not connected")

        self._apply_scene_channels(scene.channels if scene else [], dry_run=dry_run)

        if settings.light_osc_mirror:
            self._send_td_osc("/light/set_scene", cue.scene_id, fade, dry_run=dry_run)

    def blackout_signal(self, dry_run: bool = False) -> None:
        if settings.light_output == "tcp" and get_light_tcp_session().connected:
            address, args = eos_key_out()
            self._send_desk_osc(address, *args, dry_run=dry_run)
        elif settings.light_output != "tcp":
            address, args = eos_key_out()
            self._send_desk_osc(address, *args, dry_run=dry_run)

        if settings.light_osc_mirror:
            self._send_td_osc("/light/blackout", dry_run=dry_run)

    def blackout(self, dry_run: bool = False) -> None:
        self.blackout_signal(dry_run=dry_run)
        if settings.light_output == "tcp":
            get_light_tcp_session().close_session(dry_run=dry_run)
            close_light_tcp()

    def hold(self, cue: LightCue, dry_run: bool = False) -> None:
        self.send_scene(cue, dry_run=dry_run)

    def _apply_scene_channels(self, channel_specs: list[str], *, dry_run: bool) -> None:
        for channel in expand_channels(channel_specs):
            address, args = eos_chan_full(channel)
            self._send_desk_osc(address, *args, dry_run=dry_run)

    def apply_channel(self, channel: int, dry_run: bool = False) -> None:
        if settings.light_output == "tcp":
            get_light_tcp_session().open_session(dry_run=dry_run)
        address, args = eos_chan_full(channel)
        self._send_desk_osc(address, *args, dry_run=dry_run)

    def _desk_osc_target(self) -> tuple[str, int]:
        if settings.light_output == "tcp":
            return settings.light_tcp_host, settings.light_tcp_port
        return settings.osc_host, settings.osc_port

    def _send_desk_osc(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        if settings.light_output == "tcp":
            get_light_tcp_session().send_osc(address, list(args), dry_run=is_dry_run)
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

    def _send_td_osc(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        log_osc_command(
            settings.osc_host,
            settings.osc_port,
            address,
            list(args),
            dry_run=is_dry_run,
            bridge="light",
        )
        if is_dry_run or self._td_osc_client is None:
            return
        self._td_osc_client.send_message(address, list(args))
