"""Cue density curve for Teil 2 — scales scheduler intervals by anarchy level."""

from __future__ import annotations


def _lerp(low: float, high: float, t: float) -> float:
    return low + (high - low) * max(0.0, min(1.0, t))


def cue_intervals_for_anarchy(anarchy_level: float) -> dict[str, tuple[float, float]]:
    """Return (min_sec, max_sec) per medium for the given anarchy level.

    Light may change often, but never as rapid-fire: enforce a short breathing gap,
    tighter only once anarchy/chaos is high.
    """
    level = max(0.0, min(1.0, anarchy_level))
    if level <= 0.35:
        return {
            "video": (12.0, 20.0),
            "sound": (8.0, 14.0),
            "light": (8.0, 14.0),
        }
    if level <= 0.55:
        t = (level - 0.35) / 0.2
        return {
            "video": (_lerp(12.0, 8.0, t), _lerp(20.0, 14.0, t)),
            "sound": (_lerp(8.0, 6.0, t), _lerp(14.0, 10.0, t)),
            "light": (_lerp(8.0, 6.0, t), _lerp(14.0, 10.0, t)),
        }
    if level <= 0.75:
        t = (level - 0.55) / 0.2
        return {
            "video": (_lerp(8.0, 5.0, t), _lerp(14.0, 10.0, t)),
            "sound": (_lerp(6.0, 4.0, t), _lerp(10.0, 7.0, t)),
            "light": (_lerp(6.0, 4.0, t), _lerp(10.0, 7.0, t)),
        }
    t = (level - 0.75) / 0.25
    return {
        "video": (_lerp(5.0, 3.0, t), _lerp(10.0, 8.0, t)),
        "sound": (_lerp(4.0, 2.5, t), _lerp(7.0, 5.0, t)),
        "light": (_lerp(4.0, 2.0, t), _lerp(7.0, 4.0, t)),
    }


def atmosphere_intervals_for_anarchy(anarchy_level: float) -> tuple[float, float]:
    """Begleitvideo ticks — longer holds early, denser toward chaos (end stays tight)."""
    level = max(0.0, min(1.0, anarchy_level))
    if level <= 0.35:
        return (8.0, 12.0)
    if level <= 0.55:
        t = (level - 0.35) / 0.2
        return (_lerp(8.0, 5.0, t), _lerp(12.0, 7.0, t))
    if level <= 0.75:
        t = (level - 0.55) / 0.2
        return (_lerp(5.0, 3.0, t), _lerp(7.0, 5.0, t))
    t = (level - 0.75) / 0.25
    return (_lerp(3.0, 2.5, t), _lerp(5.0, 4.0, t))


def scaled_min_interval(base_min: float, anarchy_level: float) -> float:
    intervals = cue_intervals_for_anarchy(anarchy_level)
    return intervals["video"][0] if base_min <= 0 else base_min * max(0.15, 1.0 - anarchy_level * 0.85)


def light_min_interval_seconds(anarchy_level: float, *, base_min: float = 10.0) -> float:
    """Effective light gap: anarchy curve wins early; still shortens in chaos."""
    anarchy_min = cue_intervals_for_anarchy(anarchy_level)["light"][0]
    scale = max(0.05, 1.0 - anarchy_level * 0.95)
    return max(base_min * scale, anarchy_min)


def light_fade_seconds(base_fade: float, anarchy_level: float) -> float:
    """Long soft fades early; faster cuts as anarchy rises (lighting-designer curve)."""
    level = max(0.0, min(1.0, anarchy_level))
    # anarchy 0 → ~1.85×, anarchy 1 → ~0.4×
    multiplier = 1.85 - level * 1.45
    return max(0.4, round(base_fade * multiplier, 2))
