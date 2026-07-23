"""Translate DB Rule rows into the shared CanonicalRule representation."""

from __future__ import annotations

from app.models.rule import Rule
from app.services.rule_representation import CanonicalRule


def db_rule_to_canonical(row: Rule) -> CanonicalRule:
    return CanonicalRule.from_validated(
        id=row.id,
        name=row.name,
        enabled=row.enabled,
        priority=row.priority,
        conditions=list(row.conditions or []),
        actions=list(row.actions or []),
        cooldown_seconds=row.cooldown_seconds,
        production_id=row.production_id,
        source="db",
    )


def db_rules_to_canonical(rows: list[Rule]) -> list[CanonicalRule]:
    return [db_rule_to_canonical(row) for row in rows]
