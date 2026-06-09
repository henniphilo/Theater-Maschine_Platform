import structlog
from pythonosc import udp_client

from app.core.config import settings

logger = structlog.get_logger(__name__)


class TouchDesignerBridge:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.host = host or settings.osc_host
        self.port = port or settings.osc_port
        self.dry_run = settings.osc_dry_run if dry_run is None else dry_run
        self._client: udp_client.SimpleUDPClient | None = None
        if not self.dry_run:
            self._client = udp_client.SimpleUDPClient(self.host, self.port)

    def _send(self, address: str, *args: object) -> None:
        if self.dry_run or self._client is None:
            logger.info("osc_dry_run", address=address, args=args, host=self.host, port=self.port)
            return
        self._client.send_message(address, list(args))
        logger.info("osc_sent", address=address, args=args)

    def play_clip(self, clip_id: str, opacity: float = 0.8, fade_time: float = 4.0) -> None:
        self._send("/visual/play_clip", clip_id, opacity, fade_time)

    def stop_clip(self) -> None:
        self._send("/visual/stop_clip")

    def set_opacity(self, opacity: float) -> None:
        self._send("/visual/set_opacity", opacity)

    def fade(self, fade_time: float) -> None:
        self._send("/visual/fade", fade_time)

    def start_recording(self, recording_id: str) -> None:
        self._send("/visual/record_start", recording_id)

    def stop_recording(self) -> None:
        self._send("/visual/record_stop")

    def play_recording(self, recording_id: str) -> None:
        self._send("/visual/play_recording", recording_id)

    def blackout(self) -> None:
        self._send("/visual/blackout")
