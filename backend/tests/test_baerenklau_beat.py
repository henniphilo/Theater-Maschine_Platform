from app.schemas.script import ScriptBeat
from app.services.baerenklau_beat import resolve_part1_beat, resolve_part1_beats


def _beat(text: str, *, scene_title: str | None = None, order: int = 0) -> ScriptBeat:
    return ScriptBeat(id=f"beat-{order}", order=order, text=text, scene_title=scene_title, speaker="AI_A")


def test_resolve_part1_beats_returns_all_beats() -> None:
    beats = [_beat("Delphin"), _beat("Bärenklau im Keller", scene_title="Bärenklau", order=1)]
    assert [b.id for b in resolve_part1_beats(beats)] == ["beat-0", "beat-1"]


def test_resolve_part1_beats_single_whole_text() -> None:
    beats = [_beat("Gesamter Stücktext hier.")]
    assert [b.id for b in resolve_part1_beats(beats)] == ["beat-0"]


def test_resolve_part1_beat_never_none_when_beats_exist() -> None:
    assert resolve_part1_beat([_beat("Ohne Tiernamen")]) is not None
