"""Phase 2/3: Lighting output via OSC stub (Art-Net planned for Phase 3)."""

import structlog
from pythonosc import udp_client

from app.core.config import settings
from app.director.cues.cue_models import LightCue
from app.director.media.database import MediaDatabase

logger = structlog.get_logger(__name__)


class LightingBridge:
    def __init__(
        self,
        media_db: MediaDatabase | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.host = host or settings.osc_host
        self.port = port or settings.osc_port
        self._client = udp_client.SimpleUDPClient(self.host, self.port)

    def execute(self, cue: LightCue, dry_run: bool = False) -> None:
        if cue.scene_id is None:
            return
        scene = next((s for s in self.media_db.light_scenes if s.id == cue.scene_id), None)
        fade = cue.fade_time if cue.fade_time else (scene.fade_time if scene else 4.0)
        self._send("/light/set_scene", cue.scene_id, fade, dry_run=dry_run)
        if scene:
            logger.info(
                "light_scene",
                scene_id=scene.id,
                description=scene.description,
                dmx=scene.dmx,
                fade_time=fade,
            )

    def blackout(self, dry_run: bool = False) -> None:
        self._send("/light/blackout", dry_run=dry_run)

    def _send(self, address: str, *args: object, dry_run: bool = False) -> None:
        if dry_run or settings.osc_dry_run:
            logger.info("light_osc_dry_run", address=address, args=args)
            return
        self._client.send_message(address, list(args))
        logger.info("light_osc_sent", address=address, args=args)
