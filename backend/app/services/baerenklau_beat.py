import re

from app.schemas.script import ScriptBeat

_BAERENKLAU_RE = re.compile(r"bärenklau|baerenklau|bärenklauer|baerenklauer", re.IGNORECASE)


def is_baerenklau_beat(beat: ScriptBeat) -> bool:
    haystack = f"{beat.scene_title or ''} {beat.text[:400]}"
    return bool(_BAERENKLAU_RE.search(haystack))


def find_baerenklau_beats(beats: list[ScriptBeat]) -> list[ScriptBeat]:
    return [beat for beat in beats if is_baerenklau_beat(beat)]


def resolve_part1_beats(beats: list[ScriptBeat]) -> list[ScriptBeat]:
    """Teil 1: alle Beats (typisch ein Gesamttext-Beat)."""
    return list(beats)


def resolve_part1_beat(beats: list[ScriptBeat]) -> ScriptBeat | None:
    resolved = resolve_part1_beats(beats)
    return resolved[0] if resolved else None


def first_baerenklau_beat(beats: list[ScriptBeat]) -> ScriptBeat | None:
    found = find_baerenklau_beats(beats)
    return found[0] if found else None
