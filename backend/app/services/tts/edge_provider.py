import uuid
from pathlib import Path

import edge_tts

from app.core.config import settings

VOICE_CACHE = Path(__file__).resolve().parents[3] / "data" / "tts"


class EdgeTTSProvider:
    @staticmethod
    def is_available() -> bool:
        return True

    @staticmethod
    def voice_for_speaker(speaker: str) -> str:
        if speaker == "openai":
            return settings.tts_edge_voice_openai
        return settings.tts_edge_voice_anthropic

    @staticmethod
    async def list_voices() -> list[str]:
        voices = await edge_tts.list_voices()
        return [v["ShortName"] for v in voices]

    @staticmethod
    async def synthesize(text: str, speaker: str) -> Path:
        voice = EdgeTTSProvider.voice_for_speaker(speaker)
        VOICE_CACHE.mkdir(parents=True, exist_ok=True)
        path = VOICE_CACHE / f"{uuid.uuid4()}.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(path))
        return path
