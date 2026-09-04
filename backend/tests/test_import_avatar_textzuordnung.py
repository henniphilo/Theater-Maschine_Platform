"""Tests for Numbers «Zeit» duration import and catalog/media helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.services.avatar_duration import normalize_duration_ms, parse_zeit_duration_ms
from scripts.import_avatar_textzuordnung import (
    apply_media_durations,
    complete_row,
    fill_missing_durations_from_csv,
    index_media_folder,
    normalize_media_key,
    note_marks_removed,
    parse_zeit_duration_ms as import_parse_zeit,
    resolve_media_file,
    _is_catalog_header,
)


def test_parse_zeit_duration_ms_seven_seconds():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 7, 0)) == 7_000


def test_parse_zeit_duration_ms_one_minute_thirty_seconds():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 1, 30)) == 90_000


def test_import_script_uses_same_parse():
    assert import_parse_zeit(datetime(1900, 1, 1, 0, 7, 0)) == 7_000


def test_normalize_legacy_csv_duration():
    assert normalize_duration_ms(420_000) == 7_000
    assert normalize_duration_ms(540_000) == 9_000
    assert normalize_duration_ms(90_000) == 90_000


def test_parse_zeit_duration_ms_rejects_non_datetime():
    assert parse_zeit_duration_ms("not-a-duration") is None
    assert parse_zeit_duration_ms(None) is None


def test_parse_zeit_duration_ms_numbers_text_format():
    assert parse_zeit_duration_ms("00:24 Sek") == 24_000
    assert parse_zeit_duration_ms("00:07 Sek") == 7_000
    assert import_parse_zeit("00:07 Sek") == 7_000


def test_parse_zeit_duration_ms_zero_is_none():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 0, 0)) is None


def test_is_catalog_header_detects_csv_shaped_numbers():
    assert _is_catalog_header(["id", "text", "avatar", "video_clip_id", "scene_ref", "duration_ms"])
    assert not _is_catalog_header(["clip", "text", "zeit"])


def test_complete_row_fills_missing_avatar_and_clip_id():
    row = complete_row(
        {
            "id": "bak6_schwein",
            "text": "Wahrscheinlich will der Arbeiter auch bloß einen Kredit bekommen",
            "avatar": "",
            "video_clip_id": "",
            "scene_ref": "BAK6_Schwein",
        }
    )
    assert row["avatar"] == "baerenklau"
    assert row["video_clip_id"] == "bak6_schwein"
    assert row["scene_ref"] == "BAK6_Schwein"


def test_complete_row_normalizes_avatar_case():
    row = complete_row(
        {
            "id": "lg4_maeuse",
            "text": "Das Geld koennte",
            "avatar": "Lamm",
            "video_clip_id": "lg4_maeuse",
            "scene_ref": "LG4_Maeuse",
            "duration_ms": 9440,
        }
    )
    assert row["avatar"] == "lamm"
    assert row["duration_ms"] == 9440


def test_normalize_media_key_strips_spaces_and_diacritics():
    assert normalize_media_key("BAK1_Nicolas Pflanzen 3") == "bak1nicolaspflanzen3"
    assert normalize_media_key("DasLammGottes") == "daslammgottes"


def test_resolve_media_file_aliases(tmp_path: Path):
    lamm = tmp_path / "LG1_Das Lamm Gottes.mp4"
    lamm.write_bytes(b"x")
    caro = tmp_path / "MO3_Dachs_Caro.mp4"
    caro.write_bytes(b"x")
    mavie = tmp_path / "BK8_Mavie_Pflanze.mp4"
    mavie.write_bytes(b"x")
    robo = tmp_path / "PET5_Azaria_Robo.mp4"
    robo.write_bytes(b"x")
    index = index_media_folder(tmp_path)

    assert resolve_media_file(
        {"id": "daslammgottes", "scene_ref": "DasLammGottes", "video_clip_id": "daslammgottes"},
        index,
    ) == lamm
    assert resolve_media_file(
        {"id": "mo3_caro", "scene_ref": "MO3_Caro", "video_clip_id": "mo3_caro"},
        index,
    ) == caro
    assert resolve_media_file(
        {"id": "bk8_mavie", "scene_ref": "BK8_Mavie", "video_clip_id": "bk8_mavie"},
        index,
    ) == mavie
    assert resolve_media_file(
        {"id": "pet5_azaria", "scene_ref": "PET5_Azaria", "video_clip_id": "pet5_azaria"},
        index,
    ) == robo


def test_complete_row_slugs_id_and_overrides_scene_ref():
    row = complete_row(
        {
            "id": "BK7_Caroline_Geldstrudel",
            "text": "Der Kredit ist endlos.",
            "avatar": "baerenklau",
            "video_clip_id": "BK7_Caroline_Geldstrudel",
            "scene_ref": "BK7_Caroline_Geldstrudel",
        }
    )
    assert row["id"] == "bk7_caroline_geldstrudel"
    assert row["video_clip_id"] == "bk7_caroline_geldstrudel"
    assert row["scene_ref"] == "BK7_Caroline_Geldstrudel"

    stroh = complete_row(
        {
            "id": "bk3_thomas_stroh",
            "text": "und Sie gruenden immer neue Firmen",
            "avatar": "baerenklau",
            "video_clip_id": "bk3_thomas_stroh",
            "scene_ref": "BK3_Thomas",
        }
    )
    assert stroh["scene_ref"] == "BK3_Thomas_Stroh"


def test_note_marks_removed():
    assert note_marks_removed("IST GESTRICHEN !")
    assert note_marks_removed("Gelöscht")
    assert note_marks_removed("Neu PET5_Azaria_Robo") is False
    assert note_marks_removed(None) is False


def test_fill_missing_durations_from_csv(tmp_path: Path):
    csv_path = tmp_path / "Avatar Textzuordnung.csv"
    csv_path.write_text(
        "id;text;avatar;video_clip_id;scene_ref;duration_ms\n"
        "bak1_nicolaspflanzen3;x;baerenklau;bak1_nicolaspflanzen3;BAK1_NicolasPflanzen3;24160\n",
        encoding="utf-8",
    )
    rows: list[dict[str, str | int]] = [
        {
            "id": "bak1_nicolaspflanzen3",
            "text": "x",
            "avatar": "baerenklau",
            "video_clip_id": "bak1_nicolaspflanzen3",
            "scene_ref": "BAK1_NicolasPflanzen3",
        }
    ]
    assert fill_missing_durations_from_csv(rows, csv_path) == 1
    assert rows[0]["duration_ms"] == 24160


def test_apply_media_durations_overwrites_from_probe(tmp_path: Path, monkeypatch):
    clip = tmp_path / "PET3_Koala.mp4"
    clip.write_bytes(b"x")
    rows: list[dict[str, str | int]] = [
        {
            "id": "pet3_koala",
            "text": "Der Krieg ist nichts",
            "avatar": "petya",
            "video_clip_id": "pet3_koala",
            "scene_ref": "PET3_Koala",
            "duration_ms": 4000,
        }
    ]

    monkeypatch.setattr(
        "scripts.import_avatar_textzuordnung.probe_duration_ms",
        lambda path: 12480 if path.name == "PET3_Koala.mp4" else None,
    )
    updated, missing = apply_media_durations(rows, tmp_path)
    assert updated == 1
    assert missing == []
    assert rows[0]["duration_ms"] == 12480
