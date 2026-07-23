"""Evaluate CanonicalRule lists (priority + cooldown). Independent of DramaturgyEngine."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.services.rule_representation import CanonicalRule
from app.services.rule_schema import RuleAction, RuleCondition


@dataclass
class CueCandidate:
    """Minimal cue descriptor for selection actions."""

    id: str
    tags: list[str] = field(default_factory=list)
    group: str | None = None
    enabled: bool = True


@dataclass
class RuleEvalContext:
    text: str = ""
    tags: list[str] = field(default_factory=list)
    mood: str | None = None
    intensity: float = 0.0
    previous_cue_id: str | None = None
    manual_keys: set[str] = field(default_factory=set)
    now_seconds: float = 0.0
    available_cues: list[CueCandidate] = field(default_factory=list)
    rng: random.Random | None = None


@dataclass
class PlannedAction:
    action_type: str
    cue_id: str | None = None
    delay_seconds: float | None = None
    group: str | None = None
    tags: list[str] | None = None
    detail: str = ""


@dataclass
class RuleMatch:
    rule: CanonicalRule
    planned_actions: list[PlannedAction]


@dataclass
class RuleEvalResult:
    matches: list[RuleMatch]
    skipped_cooldown: list[str] = field(default_factory=list)
    skipped_disabled: list[str] = field(default_factory=list)
    skipped_conditions: list[str] = field(default_factory=list)


class RuleCooldownState:
    """Tracks last fire time per rule id for cooldown checks."""

    def __init__(self) -> None:
        self._last_fired: dict[str, float] = {}

    def last_fired(self, rule_id: str) -> float | None:
        return self._last_fired.get(rule_id)

    def mark_fired(self, rule_id: str, at: float) -> None:
        self._last_fired[rule_id] = at

    def is_cooling_down(self, rule: CanonicalRule, now: float) -> bool:
        if rule.cooldown_seconds is None or rule.cooldown_seconds <= 0:
            return False
        last = self._last_fired.get(rule.id)
        if last is None:
            return False
        return (now - last) < rule.cooldown_seconds


def condition_matches(condition: RuleCondition, ctx: RuleEvalContext) -> bool:
    t = condition.type
    if t == "text_contains":
        term = (condition.term or "").lower()
        return bool(term) and term in (ctx.text or "").lower()
    if t == "tag":
        tag = condition.tag or ""
        return tag in ctx.tags
    if t == "mood":
        return (condition.mood or "") == (ctx.mood or "")
    if t == "intensity_min":
        return ctx.intensity >= float(condition.value or 0.0)
    if t == "intensity_max":
        return ctx.intensity <= float(condition.value or 1.0)
    if t == "previous_cue":
        return ctx.previous_cue_id == condition.cue_id
    if t == "manual":
        key = condition.activation_key or ""
        return key in ctx.manual_keys
    return False


def rule_conditions_match(rule: CanonicalRule, ctx: RuleEvalContext) -> bool:
    if not rule.conditions:
        return False
    return all(condition_matches(c, ctx) for c in rule.conditions)


def resolve_action(
    action: RuleAction,
    ctx: RuleEvalContext,
) -> PlannedAction | None:
    rng = ctx.rng or random.Random()
    cues = [c for c in ctx.available_cues if c.enabled]

    if action.type == "execute_cue":
        return PlannedAction(
            action_type="execute_cue",
            cue_id=action.cue_id,
            detail=f"execute cue {action.cue_id}",
        )

    if action.type == "execute_delayed":
        return PlannedAction(
            action_type="execute_delayed",
            cue_id=action.cue_id,
            delay_seconds=action.delay_seconds,
            detail=f"execute cue {action.cue_id} after {action.delay_seconds}s",
        )

    if action.type == "select_from_group":
        group = action.group or ""
        pool = [c for c in cues if c.group == group]
        if not pool:
            return PlannedAction(
                action_type="select_from_group",
                group=group,
                detail=f"no cues in group {group}",
            )
        chosen = rng.choice(pool)
        return PlannedAction(
            action_type="select_from_group",
            cue_id=chosen.id,
            group=group,
            detail=f"selected {chosen.id} from group {group}",
        )

    if action.type == "select_random_by_tags":
        wanted = set(action.tags or [])
        pool = [c for c in cues if wanted.intersection(c.tags)]
        if not pool:
            return PlannedAction(
                action_type="select_random_by_tags",
                tags=list(wanted),
                detail=f"no cues matching tags {sorted(wanted)}",
            )
        chosen = rng.choice(pool)
        return PlannedAction(
            action_type="select_random_by_tags",
            cue_id=chosen.id,
            tags=list(wanted),
            detail=f"selected {chosen.id} for tags {sorted(wanted)}",
        )

    return None


def evaluate_rules(
    rules: list[CanonicalRule],
    ctx: RuleEvalContext,
    *,
    cooldown_state: RuleCooldownState | None = None,
    mark_fired: bool = True,
    stop_after_first_match: bool = False,
) -> RuleEvalResult:
    """Evaluate rules sorted by priority (desc), then id for stability.

    Cooldown skips a rule without consuming lower-priority matches unless
    ``stop_after_first_match`` and a higher-priority match already succeeded.
    """
    state = cooldown_state or RuleCooldownState()
    ordered = sorted(rules, key=lambda r: (-r.priority, r.id))
    matches: list[RuleMatch] = []
    skipped_cooldown: list[str] = []
    skipped_disabled: list[str] = []
    skipped_conditions: list[str] = []

    for rule in ordered:
        if not rule.enabled:
            skipped_disabled.append(rule.id)
            continue
        if state.is_cooling_down(rule, ctx.now_seconds):
            skipped_cooldown.append(rule.id)
            continue
        if not rule_conditions_match(rule, ctx):
            skipped_conditions.append(rule.id)
            continue

        planned: list[PlannedAction] = []
        for action in rule.actions:
            resolved = resolve_action(action, ctx)
            if resolved is not None:
                planned.append(resolved)

        matches.append(RuleMatch(rule=rule, planned_actions=planned))
        if mark_fired:
            state.mark_fired(rule.id, ctx.now_seconds)
        if stop_after_first_match:
            break

    return RuleEvalResult(
        matches=matches,
        skipped_cooldown=skipped_cooldown,
        skipped_disabled=skipped_disabled,
        skipped_conditions=skipped_conditions,
    )


def eval_result_to_dict(result: RuleEvalResult) -> dict[str, Any]:
    return {
        "matches": [
            {
                "rule_id": m.rule.id,
                "rule_name": m.rule.name,
                "priority": m.rule.priority,
                "source": m.rule.source,
                "planned_actions": [
                    {
                        "action_type": a.action_type,
                        "cue_id": a.cue_id,
                        "delay_seconds": a.delay_seconds,
                        "group": a.group,
                        "tags": a.tags,
                        "detail": a.detail,
                    }
                    for a in m.planned_actions
                ],
            }
            for m in result.matches
        ],
        "skipped_cooldown": list(result.skipped_cooldown),
        "skipped_disabled": list(result.skipped_disabled),
        "skipped_conditions": list(result.skipped_conditions),
    }
