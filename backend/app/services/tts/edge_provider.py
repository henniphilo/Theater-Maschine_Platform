import uuid
from pathlib import Path

import edge_tts

from app.services.tts.voice_map import VoiceProfile, voice_for_speaker as map_voice

VOICE_CACHE = Path(__file__).resolve().parents[3] / "data" / "tts"


class EdgeTTSProvider:
    @staticmethod
    def is_available() -> bool:
        return True

    @staticmethod
    def voice_for_speaker(speaker: str, *, profile: VoiceProfile | None = None) -> str:
        return map_voice(speaker, provider="edge", profile=profile)

    @staticmethod
    async def list_voices() -> list[str]:
        voices = await edge_tts.list_voices()
        return [v["ShortName"] for v in voices]

    @staticmethod
    async def synthesize(
        text: str,
        speaker: str,
        *,
        voice: str | None = None,
        profile: VoiceProfile | None = None,
    ) -> Path:
        voice = voice or EdgeTTSProvider.voice_for_speaker(speaker, profile=profile)
        VOICE_CACHE.mkdir(parents=True, exist_ok=True)
        path = VOICE_CACHE / f"{uuid.uuid4()}.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(path))
        return path
