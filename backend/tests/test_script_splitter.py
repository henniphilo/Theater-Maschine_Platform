from app.services.script_splitter import build_beats_from_text, split_source_text


def test_split_by_paragraphs() -> None:
    parts = split_source_text("Erster.\n\nZweiter.")
    assert len(parts) == 2


def test_split_by_separator() -> None:
    parts = split_source_text("A\n---\nB")
    assert parts == ["A", "B"]


def test_split_long_paragraph_into_multiple_beats() -> None:
    long_text = "Erster Satz. " * 80
    beats = build_beats_from_text(long_text.strip())
    assert len(beats) >= 2


def test_build_beats_alternates_speakers() -> None:
    beats = build_beats_from_text("A\n\nB")
    assert beats[0].speaker == "AI_A"
    assert beats[1].speaker == "AI_B"
