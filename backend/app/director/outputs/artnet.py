"""Phase 3 stub: Art-Net / sACN lighting output (not implemented yet)."""

from app.director.cues.cue_models import LightCue


class ArtNetBridge:
    """Future: send DMX universes via Art-Net for production lighting rigs."""

    def send_scene(self, cue: LightCue, channels: dict[str, int]) -> None:
        raise NotImplementedError(
            "Art-Net output is planned for Phase 3. Use LightingBridge OSC stub for now."
        )
