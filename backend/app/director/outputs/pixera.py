from pythonosc import udp_client

from app.core.config import settings
from app.director.outputs.osc_log import log_osc_command


class PixeraBridge:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.host = host or settings.pixera_osc_host or settings.osc_host
        self.port = port or settings.pixera_osc_port or settings.osc_port
        self.dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self._client: udp_client.SimpleUDPClient | None = None
        if not self.dry_run:
            self._client = udp_client.SimpleUDPClient(self.host, self.port)

    def _send(self, address: str, *args: object) -> None:
        dry_run = self.dry_run or self._client is None
        log_osc_command(
            self.host,
            self.port,
            address,
            list(args),
            dry_run=dry_run,
            bridge="pixera",
        )
        if dry_run:
            return
        self._client.send_message(address, list(args))

    def apply_cue(self, pixera_cue_name: str) -> None:
        self._send("/pixera/args/cue/apply", pixera_cue_name)
