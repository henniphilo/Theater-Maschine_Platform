from typing import Literal

from app.core.config import settings

VoiceProfile = Literal["dramaturg", "performance", "inszenierung"]


def default_profile_for_speaker(speaker: str) -> VoiceProfile:
    if speaker in ("openai", "anthropic"):
        return "dramaturg"
    return "performance"


def voice_for_speaker(
    speaker: str,
    *,
    provider: str,
    profile: VoiceProfile | None = None,
) -> str:
    resolved = profile or default_profile_for_speaker(speaker)
    if provider == "say":
        return _say_voice(speaker, resolved)
    return _edge_voice(speaker, resolved)


def _say_voice(speaker: str, profile: VoiceProfile) -> str:
    if profile == "inszenierung":
        if speaker == "AI_A":
            return settings.tts_voice_inszenierung_ai_a
        if speaker == "AI_B":
            return settings.tts_voice_inszenierung_ai_b
        if speaker == "narrator":
            return settings.tts_voice_inszenierung_narrator
    if profile == "performance" or speaker in ("AI_A", "AI_B", "narrator"):
        if speaker == "AI_A":
            return settings.tts_voice_ai_a
        if speaker == "AI_B":
            return settings.tts_voice_ai_b
        if speaker == "narrator":
            return settings.tts_voice_narrator
    if speaker == "openai":
        return settings.tts_voice_openai
    if speaker == "anthropic":
        return settings.tts_voice_anthropic
    return settings.tts_voice_narrator


def _edge_voice(speaker: str, profile: VoiceProfile) -> str:
    if profile == "inszenierung":
        if speaker == "AI_A":
            return settings.tts_edge_voice_inszenierung_ai_a
        if speaker == "AI_B":
            return settings.tts_edge_voice_inszenierung_ai_b
        if speaker == "narrator":
            return settings.tts_edge_voice_inszenierung_narrator
    if profile == "performance" or speaker in ("AI_A", "AI_B", "narrator"):
        if speaker == "AI_A":
            return settings.tts_edge_voice_ai_a
        if speaker == "AI_B":
            return settings.tts_edge_voice_ai_b
        if speaker == "narrator":
            return settings.tts_edge_voice_narrator
    if speaker == "openai":
        return settings.tts_edge_voice_openai
    if speaker == "anthropic":
        return settings.tts_edge_voice_anthropic
    return settings.tts_edge_voice_narrator
