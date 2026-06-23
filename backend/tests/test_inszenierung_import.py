import pytest

from app.services.inszenierung_import import parse_uploaded_file, parse_uploaded_files


def test_parse_json_array() -> None:
    content = '[{"animal":"Bär","title":"Szene 1","source_text":"Geld ist knapp."}]'
    scenes = parse_uploaded_file("szenen.json", content)
    assert len(scenes) == 1
    assert scenes[0].animal == "Bär"


def test_parse_txt_with_header() -> None:
    content = """Tier: Hund
Szene: Szene 3: Der Klauenvertrag

Der Hund spricht über Geld und Schuld."""
    scenes = parse_uploaded_file("import.txt", content)
    assert scenes[0].animal == "Hund"
    assert "Klauenvertrag" in scenes[0].title
    assert "Geld" in scenes[0].source_text


def test_parse_txt_from_filename() -> None:
    content = "Szene 5: Im Stall\n\nWir haben kein Geld mehr."
    scenes = parse_uploaded_file("Baer.txt", content)
    assert scenes[0].animal == "Baer"
    assert scenes[0].title.startswith("Szene 5")


def test_parse_multi_scene_txt_split() -> None:
    content = """Tier: Bär
Szene: Szene 1

Erster Text über Geld.
---
Tier: Hund
Szene: Szene 2

Zweiter Text."""
    scenes = parse_uploaded_file("korpus.txt", content)
    assert len(scenes) == 2
    assert scenes[1].animal == "Hund"


def test_parse_uploaded_files_multiple() -> None:
    files = [
        ("Baer.txt", "Text des Bären über Geld."),
        ("Hund.txt", "Text des Hundes."),
    ]
    scenes = parse_uploaded_files(files)
    assert len(scenes) == 2
    assert {s.animal for s in scenes} == {"Baer", "Hund"}


def test_empty_file_raises() -> None:
    with pytest.raises(ValueError):
        parse_uploaded_file("leer.txt", "   ")
