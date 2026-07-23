"""Shared internal rule representation for JSON and DB dramaturgy rules.

DramaturgyEngine continues to use MediaDatabase/selector directly. This module
is the migration bridge: both legacy JSON and new DB rows compile to
``CanonicalRule`` and can be evaluated by ``rule_evaluator`` without
replacing the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.services.rule_schema import RuleAction, RuleCondition, parse_actions, parse_conditions

RuleSource = Literal["db", "json"]


@dataclass(frozen=True)
class CanonicalRule:
    """Source-agnostic dramaturgy rule used by the evaluator."""

    id: str
    name: str
    enabled: bool
    priority: int
    conditions: tuple[RuleCondition, ...]
    actions: tuple[RuleAction, ...]
    cooldown_seconds: float | None = None
    production_id: str | None = None
    source: RuleSource = "db"
    meta: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_validated(
        cls,
        *,
        id: str,
        name: str,
        enabled: bool,
        priority: int,
        conditions: list[dict] | list[RuleCondition],
        actions: list[dict] | list[RuleAction],
        cooldown_seconds: float | None = None,
        production_id: str | None = None,
        source: RuleSource = "db",
        meta: dict[str, str] | None = None,
    ) -> CanonicalRule:
        parsed_conditions = (
            tuple(conditions)
            if conditions and isinstance(conditions[0], RuleCondition)
            else tuple(parse_conditions(conditions))  # type: ignore[arg-type]
        )
        parsed_actions = (
            tuple(actions)
            if actions and isinstance(actions[0], RuleAction)
            else tuple(parse_actions(actions))  # type: ignore[arg-type]
        )
        return cls(
            id=id,
            name=name,
            enabled=enabled,
            priority=priority,
            conditions=parsed_conditions,
            actions=parsed_actions,
            cooldown_seconds=cooldown_seconds,
            production_id=production_id,
            source=source,
            meta=dict(meta or {}),
        )
