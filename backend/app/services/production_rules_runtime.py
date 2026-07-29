"""Load and apply production Rules for the Director path.

Prefers DB rules of the active Production; falls back to ``dramaturgy_rules.json``.
Matched ``execute_cue`` / ``execute_delayed`` actions dispatch only via
``CueExecutionService`` — never via hardware bridges.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.director.media.database import DramaturgyRules
from app.schemas.cue import CueExecutionResult
from app.services import active_production as active_production_store
from app.services.cue_execution_service import (
    CueExecutionRejectedError,
    CueExecutionService,
)
from app.services.cue_service import CueNotFoundError
from app.services.rule_db_adapter import db_rules_to_canonical
from app.services.rule_evaluator import (
    CueCandidate,
    PlannedAction,
    RuleCooldownState,
    RuleEvalContext,
    RuleEvalResult,
    evaluate_rules,
    eval_result_to_dict,
)
from app.services.rule_json_adapter import json_rules_to_canonical
from app.services.rule_representation import CanonicalRule
from app.services.rule_service import RuleService

logger = logging.getLogger(__name__)

RuleSource = Literal["db", "json", "none"]


@dataclass
class LoadedRules:
    source: RuleSource
    production_id: str | None
    rules: list[CanonicalRule] = field(default_factory=list)


@dataclass
class DispatchedAction:
    planned: PlannedAction
    execution: CueExecutionResult | None = None
    error: str | None = None
    skipped_reason: str | None = None


@dataclass
class EvaluateAndDispatchResult:
    loaded: LoadedRules
    evaluation: RuleEvalResult
    dispatches: list[DispatchedAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        body = eval_result_to_dict(self.evaluation)
        body["production_id"] = self.loaded.production_id
        body["rules_source"] = self.loaded.source
        body["rules_count"] = len(self.loaded.rules)
        body["dispatches"] = [
            {
                "action_type": d.planned.action_type,
                "cue_id": d.planned.cue_id,
                "delay_seconds": d.planned.delay_seconds,
                "detail": d.planned.detail,
                "skipped_reason": d.skipped_reason,
                "error": d.error,
                "execution": d.execution.model_dump(mode="json") if d.execution else None,
            }
            for d in self.dispatches
        ]
        return body


def load_canonical_rules(
    db: Session,
    *,
    production_id: str | None = None,
    include_json_fallback: bool = True,
) -> LoadedRules:
    """Load CanonicalRules for a production (active if omitted).

    Prefer DB rows. If none exist and ``include_json_fallback``, use legacy JSON.
    """
    resolved_id = production_id or active_production_store.get_active_production_id()
    if resolved_id:
        rows = RuleService(db).list_rules(production_id=resolved_id)
        if rows:
            return LoadedRules(
                source="db",
                production_id=resolved_id,
                rules=db_rules_to_canonical(rows),
            )
        if include_json_fallback:
            return LoadedRules(
                source="json",
                production_id=resolved_id,
                rules=json_rules_to_canonical(production_id=resolved_id),
            )
        return LoadedRules(source="none", production_id=resolved_id, rules=[])

    if include_json_fallback:
        return LoadedRules(
            source="json",
            production_id=None,
            rules=json_rules_to_canonical(production_id=None),
        )
    return LoadedRules(source="none", production_id=None, rules=[])


def dramaturgy_rules_from_canonical(rules: list[CanonicalRule]) -> DramaturgyRules | None:
    """Best-effort rebuild of DramaturgyRules from CanonicalRule meta (import shape)."""
    keyword_tags: dict[str, list[str]] = {}
    mood_keywords: dict[str, list[str]] = {}
    intensity_boosters: list[str] = []
    min_cue_interval_seconds: dict[str, float] = {}
    found = False

    for rule in rules:
        kind = (rule.meta or {}).get("legacy_kind")
        if kind == "keyword_tag":
            tag = str((rule.meta or {}).get("tag") or "")
            for cond in rule.conditions:
                if cond.type == "text_contains" and cond.term:
                    keyword_tags.setdefault(tag, []).append(cond.term)
                    found = True
        elif kind == "mood_keyword":
            mood = str((rule.meta or {}).get("mood") or "")
            for cond in rule.conditions:
                if cond.type == "text_contains" and cond.term:
                    mood_keywords.setdefault(mood, []).append(cond.term)
                    found = True
        elif kind == "intensity_booster":
            for cond in rule.conditions:
                if cond.type == "text_contains" and cond.term:
                    intensity_boosters.append(cond.term)
                    found = True
        elif kind == "min_cue_interval":
            channel = str((rule.meta or {}).get("channel") or "")
            if channel and rule.cooldown_seconds is not None:
                min_cue_interval_seconds[channel] = float(rule.cooldown_seconds)
                found = True

    if not found:
        return None
    return DramaturgyRules(
        keyword_tags=keyword_tags,
        mood_keywords=mood_keywords,
        intensity_boosters=intensity_boosters,
        min_cue_interval_seconds=min_cue_interval_seconds,
    )


def overlay_media_db_rules_from_active(db: Session, current: DramaturgyRules) -> DramaturgyRules:
    """If active production has DB rules with legacy meta, prefer them for MediaDatabase."""
    loaded = load_canonical_rules(db, include_json_fallback=False)
    if loaded.source != "db" or not loaded.rules:
        return current
    rebuilt = dramaturgy_rules_from_canonical(loaded.rules)
    return rebuilt if rebuilt is not None else current


class ProductionRulesRuntime:
    """Evaluate production rules and dispatch cue actions via CueExecutionService."""

    def __init__(
        self,
        db: Session,
        *,
        cooldown_state: RuleCooldownState | None = None,
    ) -> None:
        self.db = db
        self.cooldown_state = cooldown_state or RuleCooldownState()
        self._execution = CueExecutionService(db)

    def load(self, *, production_id: str | None = None) -> LoadedRules:
        return load_canonical_rules(self.db, production_id=production_id)

    def evaluate(
        self,
        ctx: RuleEvalContext,
        *,
        production_id: str | None = None,
        stop_after_first_match: bool = False,
    ) -> tuple[LoadedRules, RuleEvalResult]:
        loaded = self.load(production_id=production_id)
        result = evaluate_rules(
            loaded.rules,
            ctx,
            cooldown_state=self.cooldown_state,
            stop_after_first_match=stop_after_first_match,
        )
        return loaded, result

    def evaluate_and_dispatch(
        self,
        ctx: RuleEvalContext,
        *,
        production_id: str | None = None,
        dry_run: bool = True,
        stop_after_first_match: bool = False,
    ) -> EvaluateAndDispatchResult:
        loaded, evaluation = self.evaluate(
            ctx,
            production_id=production_id,
            stop_after_first_match=stop_after_first_match,
        )
        dispatches: list[DispatchedAction] = []
        for match in evaluation.matches:
            for planned in match.planned_actions:
                dispatches.append(self._dispatch_one(planned, dry_run=dry_run))
        return EvaluateAndDispatchResult(
            loaded=loaded,
            evaluation=evaluation,
            dispatches=dispatches,
        )

    def _dispatch_one(self, planned: PlannedAction, *, dry_run: bool) -> DispatchedAction:
        if planned.action_type not in {"execute_cue", "execute_delayed"}:
            return DispatchedAction(
                planned=planned,
                skipped_reason=f"action {planned.action_type} is not an executable cue dispatch",
            )
        if not planned.cue_id:
            return DispatchedAction(planned=planned, skipped_reason="missing cue_id")
        try:
            import time

            cue = self._execution._cues.get_cue(planned.cue_id)
            now = time.monotonic()
            if cue.cooldown_seconds and cue.cooldown_seconds > 0:
                last = self.cooldown_state.last_fired(planned.cue_id)
                if last is not None and (now - last) < cue.cooldown_seconds:
                    return DispatchedAction(
                        planned=planned,
                        skipped_reason=f"cue cooldown active ({cue.cooldown_seconds}s)",
                    )
            execution = self._execution.execute_cue(cue, dry_run=dry_run)
            if cue.cooldown_seconds and cue.cooldown_seconds > 0:
                self.cooldown_state.mark_fired(planned.cue_id, now)
        except CueNotFoundError as exc:
            return DispatchedAction(planned=planned, error=str(exc))
        except CueExecutionRejectedError as exc:
            return DispatchedAction(planned=planned, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — surface to caller; never open sockets here
            logger.exception("rule dispatch failed for cue %s", planned.cue_id)
            return DispatchedAction(planned=planned, error=str(exc))
        return DispatchedAction(planned=planned, execution=execution)


def cues_as_candidates(db: Session, production_id: str) -> list[CueCandidate]:
    from app.services.cue_service import CueService

    rows = CueService(db).list_cues(production_id=production_id)
    return [
        CueCandidate(
            id=row.id,
            tags=list((row.parameters or {}).get("tags") or []),
            group=(row.parameters or {}).get("group"),
            enabled=row.enabled,
        )
        for row in rows
    ]
