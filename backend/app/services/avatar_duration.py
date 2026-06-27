"""Parse and resolve avatar clip durations (Numbers «Zeit» min:sec)."""

from __future__ import annotations

from datetime import datetime

from app.schemas.avatar_speech import AvatarSpeechCue


def parse_zeit_duration_ms(value: object) -> int | None:
    """Numbers stores min:sec as datetime; use minute + second only."""
    if not isinstance(value, datetime):
        return None
    total_sec = value.minute * 60 + value.second
    return total_sec * 1000 if total_sec > 0 else None


def estimate_duration_ms(text: str) -> int:
    chars = len(text)
    return max(4000, min(18000, 3500 + chars * 45))


def cue_duration_ms(cue: AvatarSpeechCue) -> int | None:
    if cue.duration_ms is not None and cue.duration_ms > 0:
        return cue.duration_ms
    return None


def resolve_avatar_beat_duration_ms(text: str, cues: list[AvatarSpeechCue]) -> int:
    """Numbers/cue duration takes priority; chorus uses longest clip."""
    text_est = estimate_duration_ms(text)
    known = [d for cue in cues if (d := cue_duration_ms(cue)) is not None]
    if known:
        return max(max(known), text_est)
    return text_est


def layer_duration_ms(cue: AvatarSpeechCue) -> int:
    return cue_duration_ms(cue) or estimate_duration_ms(cue.text)
