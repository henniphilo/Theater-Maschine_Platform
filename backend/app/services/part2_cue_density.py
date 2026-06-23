"""Cue density curve for Teil 2 — scales scheduler intervals by anarchy level."""

from __future__ import annotations


def _lerp(low: float, high: float, t: float) -> float:
    return low + (high - low) * max(0.0, min(1.0, t))


def cue_intervals_for_anarchy(anarchy_level: float) -> dict[str, tuple[float, float]]:
    """Return (min_sec, max_sec) per medium for the given anarchy level."""
    level = max(0.0, min(1.0, anarchy_level))
    if level <= 0.35:
        return {
            "video": (12.0, 20.0),
            "sound": (15.0, 25.0),
            "light": (20.0, 35.0),
        }
    if level <= 0.55:
        t = (level - 0.35) / 0.2
        return {
            "video": (_lerp(12.0, 8.0, t), _lerp(20.0, 14.0, t)),
            "sound": (_lerp(15.0, 10.0, t), _lerp(25.0, 18.0, t)),
            "light": (_lerp(20.0, 14.0, t), _lerp(35.0, 25.0, t)),
        }
    if level <= 0.75:
        t = (level - 0.55) / 0.2
        return {
            "video": (_lerp(8.0, 5.0, t), _lerp(14.0, 10.0, t)),
            "sound": (_lerp(10.0, 6.0, t), _lerp(18.0, 12.0, t)),
            "light": (_lerp(14.0, 10.0, t), _lerp(25.0, 18.0, t)),
        }
    t = (level - 0.75) / 0.25
    return {
        "video": (_lerp(5.0, 3.0, t), _lerp(10.0, 8.0, t)),
        "sound": (_lerp(6.0, 4.0, t), _lerp(12.0, 10.0, t)),
        "light": (_lerp(10.0, 8.0, t), _lerp(18.0, 16.0, t)),
    }


def scaled_min_interval(base_min: float, anarchy_level: float) -> float:
    intervals = cue_intervals_for_anarchy(anarchy_level)
    return intervals["video"][0] if base_min <= 0 else base_min * max(0.15, 1.0 - anarchy_level * 0.85)
