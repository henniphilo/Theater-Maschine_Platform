from app.services.dramaturgy_workshop_service import _clamp_statement
from app.services.script_splitter import (
    MIN_BEAT_LINES,
    build_beats_from_text,
    build_part1_whole_beat,
    is_section_long_enough,
    merge_short_chunks,
    split_source_text,
)


def test_build_part1_whole_beat_single_block() -> None:
    text = "Erster Satz mit Inhalt.\n\nZweiter Absatz mit mehr Text.\nDritter Satz hier."
    beats = build_part1_whole_beat(text)
    assert len(beats) == 1
    assert "Erster Satz" in beats[0].text
    assert "Zweiter Absatz" in beats[0].text
    assert beats[0].order == 0
    assert beats[0].speaker == "AI_A"


def test_build_part1_whole_beat_preserves_scene_title() -> None:
    text = "Szene 1: Im Keller\n\nVielleicht ist Erinnerung nur eine Störung."
    beats = build_part1_whole_beat(text)
    assert len(beats) == 1
    assert beats[0].scene_title == "Szene 1: Im Keller"
    assert "Erinnerung" in beats[0].text


def test_build_part1_whole_beat_empty() -> None:
    assert build_part1_whole_beat("   ") == []


def test_split_by_paragraphs() -> None:
    parts = split_source_text("Erster.\n\nZweiter.")
    assert len(parts) == 2


def test_split_by_separator() -> None:
    parts = split_source_text("A\n---\nB")
    assert parts == ["A", "B"]


def test_merge_short_paragraphs_to_min_lines() -> None:
    short = "Zeile eins.\nZeile zwei."
    merged = merge_short_chunks([short, short, short])
    assert len(merged) == 1
    assert is_section_long_enough(merged[0])


def test_build_beats_merges_short_sections() -> None:
    text = "\n\n".join(["Ein Satz hier."] * 4)
    beats = build_beats_from_text(text)
    assert len(beats) == 1
    assert is_section_long_enough(beats[0].text)


def test_split_long_paragraph_into_multiple_beats() -> None:
    long_text = "Erster Satz. " * 200
    beats = build_beats_from_text(long_text.strip())
    assert len(beats) >= 2


def test_build_beats_alternates_speakers() -> None:
    paragraph = "\n".join([f"Zeile {i} mit genug Inhalt." for i in range(MIN_BEAT_LINES)])
    text = "\n\n".join([paragraph, paragraph])
    beats = build_beats_from_text(text)
    assert len(beats) >= 2
    assert beats[0].speaker == "AI_A"
    assert beats[1].speaker == "AI_B"


def test_extract_scene_title_from_heading_line() -> None:
    from app.services.script_splitter import extract_scene_title_and_body

    title, body = extract_scene_title_and_body(
        "Szene 1: Im Keller\n\nVielleicht ist Erinnerung nur eine Störung."
    )
    assert title == "Szene 1: Im Keller"
    assert "Erinnerung" in body


def test_build_beats_splits_scene_title() -> None:
    beats = build_beats_from_text("IM KELLER\n\nErster Satz hier.\nZweiter Satz.\nDritter Satz.\nVierter Satz.")
    assert len(beats) == 1
    assert beats[0].scene_title == "IM KELLER"
    assert "Erster Satz" in beats[0].text


def test_dramaturgy_quote_excerpts() -> None:
    from app.services.script_splitter import dramaturgy_quote_excerpts

    text = "Erster Satz mit Inhalt. Zweiter Satz mit mehr Text. Dritter Satz als Schluss."
    quotes = dramaturgy_quote_excerpts(text)
    assert len(quotes) >= 2
    assert quotes[0].startswith("Erster Satz")


def test_dramaturgy_quote_excerpts_spreads_across_long_text() -> None:
    from app.services.script_splitter import dramaturgy_quote_excerpts

    sentences = [f"Satz Nummer {i} mit genug Inhalt für ein Zitat." for i in range(20)]
    text = " ".join(sentences)
    quotes = dramaturgy_quote_excerpts(text, max_excerpts=6)
    assert len(quotes) == 6
    assert quotes[0].startswith("Satz Nummer 0")
    assert "Satz Nummer 19" in quotes[-1] or quotes[-1].startswith("Satz Nummer 1")


def test_clamp_statement_at_sentence_boundary() -> None:
    long = ". ".join([f"Satz Nummer {i} mit Inhalt" for i in range(80)])
    clamped = _clamp_statement(long, max_chars=450)
    assert len(clamped) <= 450
    assert clamped.endswith(".")


def test_clamp_statement_short_unchanged() -> None:
    short = "Kurz und knapp."
    assert _clamp_statement(short, max_chars=450) == short
