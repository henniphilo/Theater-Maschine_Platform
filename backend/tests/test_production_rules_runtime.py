"""Production rules runtime — DB preferred, JSON fallback, CueExecutionService only."""

from __future__ import annotations

from app.schemas.cue import CueCreate
from app.schemas.production import ProductionCreate
from app.schemas.rule import RuleCreate
from app.services import active_production as active_production_store
from app.services.cue_service import CueService
from app.services.production_rules_runtime import (
    ProductionRulesRuntime,
    dramaturgy_rules_from_canonical,
    load_canonical_rules,
)
from app.services.production_service import ProductionService
from app.services.rule_evaluator import RuleEvalContext
from app.services.rule_json_adapter import json_rules_to_canonical
from app.services.rule_service import RuleService


def test_load_prefers_db_for_active_production(db_session, active_store) -> None:
    prod = ProductionService(db_session).create_production(ProductionCreate(name="Rules Show"))
    active_production_store.set_active_production_id(prod.id)
    RuleService(db_session).create_rule(
        RuleCreate(
            production_id=prod.id,
            name="Hallo",
            conditions=[{"type": "text_contains", "term": "hallo"}],
            actions=[{"type": "execute_cue", "cue_id": "will-set"}],
        )
    )
    loaded = load_canonical_rules(db_session)
    assert loaded.source == "db"
    assert loaded.production_id == prod.id
    assert len(loaded.rules) == 1


def test_load_falls_back_to_json_when_no_db_rules(db_session, active_store) -> None:
    prod = ProductionService(db_session).create_production(ProductionCreate(name="Empty Rules"))
    active_production_store.set_active_production_id(prod.id)
    loaded = load_canonical_rules(db_session)
    assert loaded.source == "json"
    assert loaded.production_id == prod.id
    assert len(loaded.rules) == len(json_rules_to_canonical(production_id=prod.id))


def test_dispatch_uses_cue_execution_service_only(db_session, active_store) -> None:
    prod = ProductionService(db_session).create_production(ProductionCreate(name="Dispatch"))
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=prod.id,
            name="Wait",
            cue_type="wait",
            action="wait",
            parameters={"duration_seconds": 1},
        )
    )
    RuleService(db_session).create_rule(
        RuleCreate(
            production_id=prod.id,
            name="Fire wait",
            conditions=[{"type": "text_contains", "term": "jetzt"}],
            actions=[{"type": "execute_cue", "cue_id": cue.id}],
        )
    )
    runtime = ProductionRulesRuntime(db_session)
    result = runtime.evaluate_and_dispatch(
        RuleEvalContext(text="Bitte jetzt starten"),
        production_id=prod.id,
        dry_run=True,
    )
    assert result.loaded.source == "db"
    assert len(result.evaluation.matches) == 1
    assert len(result.dispatches) == 1
    assert result.dispatches[0].execution is not None
    assert result.dispatches[0].execution.status == "planned"
    assert result.dispatches[0].execution.dry_run is True


def test_api_evaluate_and_dispatch(api_client) -> None:
    production = api_client.post("/api/v1/productions", json={"name": "API Rules"}).json()
    cue = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "W",
            "cue_type": "wait",
            "action": "wait",
            "parameters": {"duration_seconds": 1},
        },
    ).json()
    api_client.post(
        "/api/v1/rules",
        json={
            "production_id": production["id"],
            "name": "Go",
            "conditions": [{"type": "text_contains", "term": "go"}],
            "actions": [{"type": "execute_cue", "cue_id": cue["id"]}],
        },
    )
    resp = api_client.post(
        f"/api/v1/rules/evaluate-and-dispatch?production_id={production['id']}",
        json={"text": "go now", "dry_run": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rules_source"] == "db"
    assert len(body["matches"]) == 1
    assert body["dispatches"]
    assert body["dispatches"][0]["execution"]["status"] == "planned"


def test_dramaturgy_rules_from_canonical_roundtrip() -> None:
    rules = json_rules_to_canonical(production_id="p1")
    rebuilt = dramaturgy_rules_from_canonical(rules)
    assert rebuilt is not None
    assert rebuilt.keyword_tags or rebuilt.mood_keywords or rebuilt.min_cue_interval_seconds
