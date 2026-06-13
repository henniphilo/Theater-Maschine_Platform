from app.director.dramaturgy.rules_text import _rules_path, load_dramaturgy_rules


def test_load_dramaturgy_rules_from_docs() -> None:
    path = _rules_path()
    assert path is not None
    assert path.name == "dramaturgy_rules.md"
    text = load_dramaturgy_rules()
    assert "Jelinek-nahe Dramaturgieprinzipien" in text
    assert "Keine Illustration" in text
    assert "Video, Sound und Licht" in text
