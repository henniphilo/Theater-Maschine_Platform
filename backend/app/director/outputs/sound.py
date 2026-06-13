"""Phase 2/3: Sound output via OSC (QLab/Ableton) or logging."""

from pythonosc import udp_client

from app.core.config import settings
from app.director.cues.cue_models import SoundCue
from app.director.outputs.osc_log import log_osc_command


class SoundBridge:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or settings.osc_host
        self.port = port or settings.osc_port
        self._client = udp_client.SimpleUDPClient(self.host, self.port)

    def execute(self, cue: SoundCue, dry_run: bool = False) -> None:
        if cue.cue_id is None:
            return
        if cue.action.value == "trigger_cue":
            self._send("/sound/trigger", cue.cue_id, cue.volume, dry_run=dry_run)
        elif cue.action.value == "stop_cue":
            self._send("/sound/stop", cue.cue_id, dry_run=dry_run)
        elif cue.action.value == "set_volume":
            self._send("/sound/volume", cue.cue_id, cue.volume, dry_run=dry_run)

    def hold(self, cue: SoundCue, dry_run: bool = False) -> None:
        if cue.cue_id is None:
            return
        self._send("/sound/hold", cue.cue_id, cue.volume, dry_run=dry_run)

    def stop_all(self, dry_run: bool = False) -> None:
        self._send("/sound/stop_all", dry_run=dry_run)

    def _send(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        log_osc_command(
            self.host,
            self.port,
            address,
            list(args),
            dry_run=is_dry_run,
            bridge="sound",
        )
        if is_dry_run:
            return
        self._client.send_message(address, list(args))
