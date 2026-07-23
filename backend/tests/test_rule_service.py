from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.production import ProductionCreate
from app.schemas.rule import RuleCreate, RuleEvaluateRequest, RuleUpdate
from app.services.rule_db_adapter import db_rule_to_canonical
from app.services.rule_service import RuleService, RuleValidationError
from app.services.production_service import ProductionService


def _production(db_session, active_store) -> str:
    return ProductionService(db_session).create_production(ProductionCreate(name="Rules")).id


def test_create_rejects_empty_conditions(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    with pytest.raises(ValidationError):
        RuleCreate(
            production_id=production_id,
            name="Bad",
            conditions=[],
            actions=[{"type": "execute_cue", "cue_id": "c1"}],
        )


def test_create_rejects_unknown_condition_type(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    with pytest.raises(ValidationError):
        RuleCreate(
            production_id=production_id,
            name="Bad",
            conditions=[{"type": "unknown"}],
            actions=[{"type": "execute_cue", "cue_id": "c1"}],
        )


def test_crud_and_db_to_canonical(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    service = RuleService(db_session)

    row = service.create_rule(
        RuleCreate(
            production_id=production_id,
            name="Fear flash",
            priority=20,
            cooldown_seconds=8.0,
            conditions=[
                {"type": "tag", "tag": "fear"},
                {"type": "intensity_min", "value": 0.5},
            ],
            actions=[{"type": "execute_cue", "cue_id": "flash-1"}],
        )
    )
    assert row.enabled is True
    assert row.conditions[0]["type"] == "tag"

    canonical = db_rule_to_canonical(row)
    assert canonical.source == "db"
    assert canonical.priority == 20
    assert canonical.conditions[0].tag == "fear"
    assert canonical.actions[0].cue_id == "flash-1"

    listed = service.list_rules(production_id=production_id)
    assert len(listed) == 1

    updated = service.update_rule(row.id, RuleUpdate(enabled=False, priority=1))
    assert updated.enabled is False
    assert updated.priority == 1

    service.delete_rule(row.id)
    assert service.list_rules(production_id=production_id) == []


def test_evaluate_priority_and_cooldown_via_service(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    service = RuleService(db_session)

    service.create_rule(
        RuleCreate(
            production_id=production_id,
            name="High",
            priority=100,
            cooldown_seconds=10.0,
            conditions=[{"type": "text_contains", "term": "maschine"}],
            actions=[{"type": "execute_cue", "cue_id": "high-cue"}],
        )
    )
    service.create_rule(
        RuleCreate(
            production_id=production_id,
            name="Low",
            priority=1,
            conditions=[{"type": "text_contains", "term": "maschine"}],
            actions=[{"type": "execute_cue", "cue_id": "low-cue"}],
        )
    )

    from app.services.rule_evaluator import RuleCooldownState

    state = RuleCooldownState()
    first = service.evaluate(
        production_id,
        RuleEvaluateRequest(text="die maschine läuft", now_seconds=0.0),
        cooldown_state=state,
    )
    assert [m["rule_name"] for m in first["matches"]] == ["High", "Low"]

    second = service.evaluate(
        production_id,
        RuleEvaluateRequest(text="die maschine läuft", now_seconds=3.0),
        cooldown_state=state,
    )
    assert second["skipped_cooldown"]  # high still cooling
    assert [m["rule_name"] for m in second["matches"]] == ["Low"]


def test_create_rejects_missing_production(db_session, active_store) -> None:
    service = RuleService(db_session)
    with pytest.raises(RuleValidationError):
        service.create_rule(
            RuleCreate(
                production_id="missing",
                name="X",
                conditions=[{"type": "manual", "activation_key": "go"}],
                actions=[{"type": "execute_cue", "cue_id": "c"}],
            )
        )
