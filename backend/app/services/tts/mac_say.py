import platform
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from app.core.config import settings

VOICE_CACHE = Path(__file__).resolve().parents[3] / "data" / "tts"


class MacSayProvider:
    @staticmethod
    def is_available() -> bool:
        return platform.system() == "Darwin" and shutil.which("say") is not None

    @staticmethod
    def voice_for_speaker(speaker: str) -> str:
        if speaker == "openai":
            return settings.tts_voice_openai
        return settings.tts_voice_anthropic

    @staticmethod
    def list_voices() -> list[str]:
        if not MacSayProvider.is_available():
            return []
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True, timeout=30)
        voices: list[str] = []
        for line in result.stdout.splitlines():
            match = re.match(r"^(\S+(?:\s+\([^)]+\))?)", line.strip())
            if match:
                voices.append(match.group(1))
        return voices

    @staticmethod
    def synthesize(text: str, speaker: str) -> Path:
        if not MacSayProvider.is_available():
            raise RuntimeError("macOS say ist nicht verfügbar.")
        voice = MacSayProvider.voice_for_speaker(speaker)
        VOICE_CACHE.mkdir(parents=True, exist_ok=True)
        aiff = VOICE_CACHE / f"{uuid.uuid4()}.aiff"
        subprocess.run(
            ["say", "-v", voice, "-o", str(aiff), text],
            check=True,
            timeout=180,
        )
        m4a = aiff.with_suffix(".m4a")
        if shutil.which("afconvert"):
            subprocess.run(
                ["afconvert", "-f", "mp4f", "-d", "aac", str(aiff), str(m4a)],
                check=True,
                timeout=60,
            )
            aiff.unlink(missing_ok=True)
            return m4a
        return aiff
