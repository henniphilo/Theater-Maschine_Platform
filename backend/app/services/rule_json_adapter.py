"""Translate legacy ``dramaturgy_rules.json`` into CanonicalRule list.

The JSON file is keyword/mood/interval metadata, not if-then rules. This adapter
projects that metadata into MVP condition/action rules so JSON and DB share one
evaluator path. DramaturgyEngine keeps using MediaDatabase.rules unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.director.media.database import DramaturgyRules, MediaDatabase
from app.services.rule_representation import CanonicalRule
from app.services.rule_schema import RuleAction, RuleCondition


def _resolve_rules_path(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir) / "dramaturgy_rules.json"

    configured = Path(settings.director_data_dir)
    candidates: list[Path] = []
    if configured.is_absolute():
        candidates.append(configured / "dramaturgy_rules.json")
    else:
        candidates.append(Path.cwd() / configured / "dramaturgy_rules.json")

    # Same search roots as MediaDatabase — find repo data/ when cwd is backend/.
    module_root = Path(__file__).resolve()
    for root in (module_root.parents[3], module_root.parents[2], Path.cwd(), Path.cwd().parent):
        candidates.append(root / "data" / "dramaturgy_rules.json")
        if not configured.is_absolute():
            candidates.append(root / configured / "dramaturgy_rules.json")

    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_legacy_rules_dict(data_dir: Path | None = None) -> dict[str, Any]:
    path = _resolve_rules_path(data_dir)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("dramaturgy_rules.json must be an object")
    return data


def dramaturgy_rules_dataclass_to_dict(rules: DramaturgyRules) -> dict[str, Any]:
    return {
        "keyword_tags": dict(rules.keyword_tags),
        "mood_keywords": dict(rules.mood_keywords),
        "intensity_boosters": list(rules.intensity_boosters),
        "min_cue_interval_seconds": dict(rules.min_cue_interval_seconds),
    }


def json_rules_to_canonical(
    raw: dict[str, Any] | None = None,
    *,
    data_dir: Path | None = None,
    production_id: str | None = None,
    media_db: MediaDatabase | None = None,
) -> list[CanonicalRule]:
    """Compile legacy JSON (or MediaDatabase.rules) into CanonicalRule list."""
    if raw is None and media_db is not None:
        raw = dramaturgy_rules_dataclass_to_dict(media_db.rules)
    if raw is None:
        raw = load_legacy_rules_dict(data_dir)

    rules: list[CanonicalRule] = []
    rules.extend(_keyword_tag_rules(raw.get("keyword_tags") or {}, production_id))
    rules.extend(_mood_keyword_rules(raw.get("mood_keywords") or {}, production_id))
    rules.extend(_intensity_booster_rules(raw.get("intensity_boosters") or [], production_id))
    rules.extend(
        _interval_cooldown_rules(raw.get("min_cue_interval_seconds") or {}, production_id)
    )
    return rules


def _keyword_tag_rules(
    keyword_tags: dict[str, list[str]],
    production_id: str | None,
) -> list[CanonicalRule]:
    out: list[CanonicalRule] = []
    for tag, keywords in keyword_tags.items():
        for index, term in enumerate(keywords):
            term_clean = str(term).strip()
            if not term_clean:
                continue
            rule_id = f"json:keyword:{tag}:{index}"
            out.append(
                CanonicalRule.from_validated(
                    id=rule_id,
                    name=f"Keyword „{term_clean}“ → Tag {tag}",
                    enabled=True,
                    priority=10,
                    conditions=[
                        RuleCondition(type="text_contains", term=term_clean),
                    ],
                    actions=[
                        RuleAction(type="select_random_by_tags", tags=[str(tag)]),
                    ],
                    cooldown_seconds=None,
                    production_id=production_id,
                    source="json",
                    meta={"legacy_kind": "keyword_tag", "tag": str(tag)},
                )
            )
    return out


def _mood_keyword_rules(
    mood_keywords: dict[str, list[str]],
    production_id: str | None,
) -> list[CanonicalRule]:
    out: list[CanonicalRule] = []
    for mood, keywords in mood_keywords.items():
        for index, term in enumerate(keywords):
            term_clean = str(term).strip()
            if not term_clean:
                continue
            rule_id = f"json:mood:{mood}:{index}"
            out.append(
                CanonicalRule.from_validated(
                    id=rule_id,
                    name=f"Keyword „{term_clean}“ → Mood {mood}",
                    enabled=True,
                    priority=5,
                    conditions=[
                        RuleCondition(type="text_contains", term=term_clean),
                    ],
                    actions=[
                        # Mood detection projects to tag-based cue pick using mood name.
                        RuleAction(type="select_random_by_tags", tags=[str(mood)]),
                    ],
                    cooldown_seconds=None,
                    production_id=production_id,
                    source="json",
                    meta={"legacy_kind": "mood_keyword", "mood": str(mood)},
                )
            )
    return out


def _intensity_booster_rules(
    boosters: list[str],
    production_id: str | None,
) -> list[CanonicalRule]:
    out: list[CanonicalRule] = []
    for index, term in enumerate(boosters):
        term_clean = str(term).strip()
        if not term_clean:
            continue
        rule_id = f"json:intensity_booster:{index}"
        out.append(
            CanonicalRule.from_validated(
                id=rule_id,
                name=f"Intensity booster „{term_clean}“",
                enabled=True,
                priority=3,
                conditions=[
                    RuleCondition(type="text_contains", term=term_clean),
                    RuleCondition(type="intensity_min", value=0.0),
                ],
                actions=[
                    RuleAction(type="select_random_by_tags", tags=["intensity_boost"]),
                ],
                cooldown_seconds=None,
                production_id=production_id,
                source="json",
                meta={"legacy_kind": "intensity_booster"},
            )
        )
    return out


def _interval_cooldown_rules(
    intervals: dict[str, float],
    production_id: str | None,
) -> list[CanonicalRule]:
    """Encode min_cue_interval_seconds as group-selection rules with cooldown.

    Condition is manual so these do not auto-fire on dialogue; they document
    channel cooldowns and are available when manually activated per channel.
    """
    out: list[CanonicalRule] = []
    for channel, seconds in intervals.items():
        try:
            cooldown = float(seconds)
        except (TypeError, ValueError):
            continue
        if cooldown < 0:
            continue
        channel_clean = str(channel).strip()
        if not channel_clean:
            continue
        rule_id = f"json:interval:{channel_clean}"
        out.append(
            CanonicalRule.from_validated(
                id=rule_id,
                name=f"Min interval {channel_clean} ({cooldown:g}s)",
                enabled=True,
                priority=0,
                conditions=[
                    RuleCondition(type="manual", activation_key=f"interval:{channel_clean}"),
                ],
                actions=[
                    RuleAction(type="select_from_group", group=channel_clean),
                ],
                cooldown_seconds=cooldown,
                production_id=production_id,
                source="json",
                meta={"legacy_kind": "min_cue_interval", "channel": channel_clean},
            )
        )
    return out
