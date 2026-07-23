"""CRUD and evaluation service for production Rules."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.production import Production
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleEvaluateRequest, RuleUpdate
from app.services.rule_db_adapter import db_rules_to_canonical
from app.services.rule_evaluator import (
    CueCandidate,
    RuleCooldownState,
    RuleEvalContext,
    evaluate_rules,
    eval_result_to_dict,
)
from app.services.rule_json_adapter import json_rules_to_canonical
from app.services.rule_schema import validate_actions, validate_conditions


class RuleError(Exception):
    """Base service error."""


class RuleNotFoundError(RuleError):
    pass


class RuleValidationError(RuleError):
    pass


class RuleService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_rules(
        self,
        *,
        production_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[Rule]:
        stmt = select(Rule).order_by(Rule.priority.desc(), Rule.created_at.desc())
        if production_id is not None:
            stmt = stmt.where(Rule.production_id == production_id)
        if enabled is not None:
            stmt = stmt.where(Rule.enabled.is_(enabled))
        return list(self.db.scalars(stmt).all())

    def get_rule(self, rule_id: str, *, production_id: str | None = None) -> Rule:
        row = self.db.get(Rule, rule_id)
        if row is None:
            raise RuleNotFoundError(f"Rule {rule_id} not found")
        if production_id is not None and row.production_id != production_id:
            raise RuleNotFoundError(f"Rule {rule_id} not found")
        return row

    def create_rule(self, payload: RuleCreate) -> Rule:
        if self.db.get(Production, payload.production_id) is None:
            raise RuleValidationError(f"production {payload.production_id} not found")

        row = Rule(
            production_id=payload.production_id,
            name=payload.name,
            enabled=payload.enabled,
            priority=payload.priority,
            conditions=list(payload.conditions),
            actions=list(payload.actions),
            cooldown_seconds=payload.cooldown_seconds,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_rule(self, rule_id: str, payload: RuleUpdate) -> Rule:
        row = self.get_rule(rule_id)
        data = payload.model_dump(exclude_unset=True)
        clear_cooldown = bool(data.pop("clear_cooldown_seconds", False))

        if "name" in data and data["name"] is not None:
            row.name = data["name"]
        if "enabled" in data and data["enabled"] is not None:
            row.enabled = data["enabled"]
        if "priority" in data and data["priority"] is not None:
            row.priority = data["priority"]
        if "conditions" in data and data["conditions"] is not None:
            try:
                row.conditions = validate_conditions(data["conditions"])
            except ValueError as exc:
                raise RuleValidationError(str(exc)) from exc
        if "actions" in data and data["actions"] is not None:
            try:
                row.actions = validate_actions(data["actions"])
            except ValueError as exc:
                raise RuleValidationError(str(exc)) from exc
        if clear_cooldown:
            row.cooldown_seconds = None
        elif "cooldown_seconds" in data:
            row.cooldown_seconds = data["cooldown_seconds"]

        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_rule(self, rule_id: str, *, production_id: str | None = None) -> None:
        row = self.get_rule(rule_id, production_id=production_id)
        self.db.delete(row)
        self.db.commit()

    def evaluate(
        self,
        production_id: str,
        payload: RuleEvaluateRequest,
        *,
        cooldown_state: RuleCooldownState | None = None,
    ) -> dict:
        if self.db.get(Production, production_id) is None:
            raise RuleValidationError(f"production {production_id} not found")

        db_rows = self.list_rules(production_id=production_id)
        canonical = db_rules_to_canonical(db_rows)
        if payload.include_legacy_json:
            canonical.extend(json_rules_to_canonical(production_id=production_id))

        cues = [
            CueCandidate(
                id=str(item.get("id", "")),
                tags=[str(t) for t in (item.get("tags") or [])],
                group=item.get("group"),
                enabled=bool(item.get("enabled", True)),
            )
            for item in payload.available_cues
            if item.get("id")
        ]

        ctx = RuleEvalContext(
            text=payload.text,
            tags=list(payload.tags),
            mood=payload.mood,
            intensity=payload.intensity,
            previous_cue_id=payload.previous_cue_id,
            manual_keys=set(payload.manual_keys),
            now_seconds=payload.now_seconds,
            available_cues=cues,
        )
        result = evaluate_rules(
            canonical,
            ctx,
            cooldown_state=cooldown_state,
            stop_after_first_match=payload.stop_after_first_match,
        )
        body = eval_result_to_dict(result)
        body["production_id"] = production_id
        return body
