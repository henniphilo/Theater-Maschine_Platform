from pathlib import Path

import pytest

from app.director.media.sound_inventory import load_sound_cues_from_csv, resolve_sound_overview_path
from app.services.sound_cue_catalog import SoundCueCatalogService
try:
    from tests.repo_paths import repo_data_dir
except ModuleNotFoundError:
    from repo_paths import repo_data_dir


def test_resolve_sound_overview_csv_exists() -> None:
    path = resolve_sound_overview_path(repo_data_dir())
    assert path is not None
    assert path.name == "Sound Übersicht.csv"


def test_load_csv_includes_fade_cues() -> None:
    path = resolve_sound_overview_path(repo_data_dir())
    assert path is not None
    catalog = load_sound_cues_from_csv(path)
    ids = {c.id for c in catalog.cues}
    assert "maschinen_grundader" in ids
    assert "maschinen_grundader_fade_in" in ids
    assert "maschinen_grundader_fade_out" in ids
    fade_in = next(c for c in catalog.cues if c.id == "maschinen_grundader_fade_in")
    assert fade_in.midi_note == 52
    assert fade_in.action == "fade_in"
    assert fade_in.soundname == "Maschinen-Grundader"


def test_catalog_service_loads_from_csv() -> None:
    service = SoundCueCatalogService()
    catalog = service.load()
    assert len(catalog.cues) >= 24
    mapping = service.to_midi_map(catalog)
    assert mapping["kaefigecho"].note == 37


def test_media_catalog_exposes_midi_sounds() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    res = client.get("/api/v1/media/catalog")
    assert res.status_code == 200
    sounds = res.json()["sounds"]
    assert any(s["id"] == "maschinen_grundader" for s in sounds)
    play = next(s for s in sounds if s["id"] == "maschinen_grundader")
    assert play["midi_note"] == 36
    assert play.get("soundname") == "Maschinen-Grundader"


def test_csv_roundtrip_write_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "Sound Übersicht.csv"
    csv_path.write_text(
        "cue_id;midi_note;kanal;soundname;aktion;beschreibung;tags;stimmungen\n"
        "test_sound;40;1;Test Sound;play;Beschreibung;tag;neutral\n"
        "test_sound_fade_in;50;1;Test Sound;fade_in;Ein;tag;neutral\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.director.media.sound_inventory.resolve_sound_overview_path",
        lambda _data_dir: csv_path,
    )
    monkeypatch.setattr(
        "app.services.sound_cue_catalog.resolve_sound_overview_path",
        lambda _data_dir: csv_path,
    )
    monkeypatch.setattr(
        "app.services.sound_cue_catalog.settings.director_data_dir",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "app.services.sound_cue_catalog.settings.sound_cues_path",
        str(tmp_path / "sound_cues.json"),
    )
    catalog = SoundCueCatalogService().load()
    assert len(catalog.cues) == 2
    assert (tmp_path / "sound_cues.json").is_file()
