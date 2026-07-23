"""Tests for JSON → CanonicalRule adapter (legacy dramaturgy_rules.json)."""

from __future__ import annotations

from pathlib import Path

from app.services.rule_json_adapter import json_rules_to_canonical, load_legacy_rules_dict


SAMPLE = {
    "keyword_tags": {
        "memory": ["erinnerung", "archive"],
        "fear": ["angst"],
    },
    "mood_keywords": {
        "warm": ["nähe"],
    },
    "intensity_boosters": ["!!!"],
    "min_cue_interval_seconds": {
        "video": 5.0,
        "sound": 3.0,
    },
}


def test_json_adapter_compiles_keyword_mood_interval() -> None:
    rules = json_rules_to_canonical(SAMPLE, production_id="prod-1")
    assert all(r.source == "json" for r in rules)
    assert all(r.production_id == "prod-1" for r in rules)

    keyword = [r for r in rules if r.meta.get("legacy_kind") == "keyword_tag"]
    assert len(keyword) == 3
    memory = next(r for r in keyword if r.meta.get("tag") == "memory" and "erinnerung" in r.name)
    assert memory.conditions[0].type == "text_contains"
    assert memory.conditions[0].term == "erinnerung"
    assert memory.actions[0].type == "select_random_by_tags"
    assert memory.actions[0].tags == ["memory"]
    assert memory.priority == 10

    mood = [r for r in rules if r.meta.get("legacy_kind") == "mood_keyword"]
    assert len(mood) == 1
    assert mood[0].priority == 5

    boosters = [r for r in rules if r.meta.get("legacy_kind") == "intensity_booster"]
    assert len(boosters) == 1

    intervals = [r for r in rules if r.meta.get("legacy_kind") == "min_cue_interval"]
    assert len(intervals) == 2
    video = next(r for r in intervals if r.meta.get("channel") == "video")
    assert video.cooldown_seconds == 5.0
    assert video.conditions[0].type == "manual"
    assert video.actions[0].type == "select_from_group"


def test_load_real_dramaturgy_rules_json() -> None:
    """Uses repo data/ when present — smoke that adapter accepts production file."""
    repo_data = Path(__file__).resolve().parents[2] / "data"
    raw = load_legacy_rules_dict(repo_data)
    if not raw:
        return
    rules = json_rules_to_canonical(raw)
    assert len(rules) > 0
    assert any(r.meta.get("legacy_kind") == "keyword_tag" for r in rules)
