import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.services.tts.voice_map import VoiceProfile, voice_for_speaker as map_voice

VOICE_CACHE = Path(__file__).resolve().parents[3] / "data" / "tts"


class MacSayProvider:
    @staticmethod
    def is_available() -> bool:
        return platform.system() == "Darwin" and shutil.which("say") is not None

    @staticmethod
    def voice_for_speaker(speaker: str, *, profile: VoiceProfile | None = None) -> str:
        return map_voice(speaker, provider="say", profile=profile)

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
    def synthesize(
        text: str,
        speaker: str,
        *,
        voice: str | None = None,
        profile: VoiceProfile | None = None,
    ) -> Path:
        if not MacSayProvider.is_available():
            raise RuntimeError("macOS say ist nicht verfügbar.")
        voice = voice or MacSayProvider.voice_for_speaker(speaker, profile=profile)
        VOICE_CACHE.mkdir(parents=True, exist_ok=True)
        aiff = VOICE_CACHE / f"{uuid.uuid4()}.aiff"
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as text_file:
            text_file.write(text)
            text_path = text_file.name
        try:
            subprocess.run(
                ["say", "-v", voice, "-o", str(aiff), "-f", text_path],
                check=True,
                timeout=180,
            )
        finally:
            Path(text_path).unlink(missing_ok=True)
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
