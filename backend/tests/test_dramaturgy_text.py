from app.services.dramaturgy_text import clamp_statement, strip_limit_complaints


def test_strip_limit_complaints() -> None:
    raw = (
        "Ich hebe die 450-Zeichen-Grenze auf.\n"
        "«Stichwort» — kühle Stimmung (Sound)."
    )
    cleaned = strip_limit_complaints(raw)
    assert "450" not in cleaned
    assert "Stichwort" in cleaned


def test_clamp_statement_respects_limit() -> None:
    long = "Wort " * 200
    result = clamp_statement(long, max_chars=450)
    assert len(result) <= 450
