"""Tests for Numbers «Zeit» duration import."""

from __future__ import annotations

from datetime import datetime

from scripts.import_avatar_textzuordnung import parse_zeit_duration_ms


def test_parse_zeit_duration_ms_seven_minutes():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 7, 0)) == 420_000


def test_parse_zeit_duration_ms_one_minute_thirty_seconds():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 1, 30)) == 90_000


def test_parse_zeit_duration_ms_rejects_non_datetime():
    assert parse_zeit_duration_ms("7:00") is None
    assert parse_zeit_duration_ms(None) is None


def test_parse_zeit_duration_ms_zero_is_none():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 0, 0)) is None
