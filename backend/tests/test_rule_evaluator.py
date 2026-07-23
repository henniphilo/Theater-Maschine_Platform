"""Unit tests for CanonicalRule evaluation: conditions, priority, cooldown."""

from __future__ import annotations

import random

from app.services.rule_evaluator import (
    CueCandidate,
    RuleCooldownState,
    RuleEvalContext,
    evaluate_rules,
    rule_conditions_match,
)
from app.services.rule_representation import CanonicalRule
from app.services.rule_schema import RuleAction, RuleCondition


def _rule(
    *,
    id: str,
    priority: int = 0,
    enabled: bool = True,
    cooldown: float | None = None,
    conditions: list[RuleCondition] | None = None,
    actions: list[RuleAction] | None = None,
) -> CanonicalRule:
    return CanonicalRule.from_validated(
        id=id,
        name=id,
        enabled=enabled,
        priority=priority,
        conditions=conditions
        or [RuleCondition(type="text_contains", term="hallo")],
        actions=actions or [RuleAction(type="execute_cue", cue_id="cue-a")],
        cooldown_seconds=cooldown,
        source="db",
    )


def test_all_mvp_conditions() -> None:
    ctx = RuleEvalContext(
        text="Die Erinnerung an Angst",
        tags=["memory", "fear"],
        mood="unheimlich",
        intensity=0.7,
        previous_cue_id="cue-prev",
        manual_keys={"go"},
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="text_contains", term="erinnerung")]),
        ctx,
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="tag", tag="fear")]),
        ctx,
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="mood", mood="unheimlich")]),
        ctx,
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="intensity_min", value=0.5)]),
        ctx,
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="intensity_max", value=0.8)]),
        ctx,
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="previous_cue", cue_id="cue-prev")]),
        ctx,
    )
    assert rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="manual", activation_key="go")]),
        ctx,
    )
    assert not rule_conditions_match(
        _rule(id="t", conditions=[RuleCondition(type="intensity_min", value=0.9)]),
        ctx,
    )


def test_conditions_are_anded() -> None:
    rule = _rule(
        id="and",
        conditions=[
            RuleCondition(type="tag", tag="memory"),
            RuleCondition(type="intensity_min", value=0.6),
        ],
    )
    assert rule_conditions_match(
        rule,
        RuleEvalContext(tags=["memory"], intensity=0.7),
    )
    assert not rule_conditions_match(
        rule,
        RuleEvalContext(tags=["memory"], intensity=0.2),
    )


def test_priority_orders_matches_and_stop_after_first() -> None:
    low = _rule(id="low", priority=1)
    high = _rule(id="high", priority=100)
    mid = _rule(id="mid", priority=50)
    ctx = RuleEvalContext(text="hallo welt")

    all_matches = evaluate_rules([low, mid, high], ctx, mark_fired=False)
    assert [m.rule.id for m in all_matches.matches] == ["high", "mid", "low"]

    first = evaluate_rules(
        [low, mid, high],
        ctx,
        mark_fired=False,
        stop_after_first_match=True,
    )
    assert [m.rule.id for m in first.matches] == ["high"]


def test_disabled_rules_skipped() -> None:
    rule = _rule(id="off", enabled=False)
    result = evaluate_rules([rule], RuleEvalContext(text="hallo"))
    assert result.matches == []
    assert result.skipped_disabled == ["off"]


def test_cooldown_skips_then_allows_after_window() -> None:
    rule = _rule(id="cd", cooldown=10.0)
    state = RuleCooldownState()
    ctx1 = RuleEvalContext(text="hallo", now_seconds=100.0)
    first = evaluate_rules([rule], ctx1, cooldown_state=state, mark_fired=True)
    assert len(first.matches) == 1

    ctx2 = RuleEvalContext(text="hallo", now_seconds=105.0)
    second = evaluate_rules([rule], ctx2, cooldown_state=state, mark_fired=True)
    assert second.matches == []
    assert second.skipped_cooldown == ["cd"]

    ctx3 = RuleEvalContext(text="hallo", now_seconds=110.0)
    third = evaluate_rules([rule], ctx3, cooldown_state=state, mark_fired=True)
    assert len(third.matches) == 1


def test_higher_priority_cooldown_does_not_block_lower() -> None:
    high = _rule(id="high", priority=10, cooldown=30.0)
    low = _rule(id="low", priority=1, cooldown=None)
    state = RuleCooldownState()
    ctx = RuleEvalContext(text="hallo", now_seconds=0.0)
    evaluate_rules([high, low], ctx, cooldown_state=state, mark_fired=True)

    again = evaluate_rules(
        [high, low],
        RuleEvalContext(text="hallo", now_seconds=5.0),
        cooldown_state=state,
        mark_fired=True,
    )
    assert again.skipped_cooldown == ["high"]
    assert [m.rule.id for m in again.matches] == ["low"]


def test_action_select_random_by_tags_deterministic_rng() -> None:
    rule = _rule(
        id="pick",
        conditions=[RuleCondition(type="tag", tag="memory")],
        actions=[RuleAction(type="select_random_by_tags", tags=["memory"])],
    )
    cues = [
        CueCandidate(id="a", tags=["memory"]),
        CueCandidate(id="b", tags=["memory"]),
        CueCandidate(id="c", tags=["fear"]),
    ]
    ctx = RuleEvalContext(
        tags=["memory"],
        available_cues=cues,
        rng=random.Random(1),
    )
    result = evaluate_rules([rule], ctx, mark_fired=False)
    assert len(result.matches) == 1
    planned = result.matches[0].planned_actions[0]
    assert planned.cue_id in {"a", "b"}
    assert planned.action_type == "select_random_by_tags"


def test_execute_delayed_and_group_selection() -> None:
    delayed = _rule(
        id="delay",
        conditions=[RuleCondition(type="manual", activation_key="go")],
        actions=[RuleAction(type="execute_delayed", cue_id="cue-x", delay_seconds=2.5)],
    )
    group = _rule(
        id="grp",
        priority=1,
        conditions=[RuleCondition(type="manual", activation_key="go")],
        actions=[RuleAction(type="select_from_group", group="video")],
    )
    ctx = RuleEvalContext(
        manual_keys={"go"},
        available_cues=[
            CueCandidate(id="v1", group="video"),
            CueCandidate(id="s1", group="sound"),
        ],
        rng=random.Random(0),
    )
    result = evaluate_rules([delayed, group], ctx, mark_fired=False)
    by_id = {m.rule.id: m for m in result.matches}
    assert by_id["delay"].planned_actions[0].delay_seconds == 2.5
    assert by_id["grp"].planned_actions[0].cue_id == "v1"
