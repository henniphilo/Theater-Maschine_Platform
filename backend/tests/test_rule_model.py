from __future__ import annotations

from app.models.rule import Rule
from app.schemas.production import ProductionCreate
from app.schemas.rule import RuleCreate
from app.services.production_service import ProductionService
from app.services.rule_service import RuleService


def test_rule_model_persists_json_structures(db_session, active_store) -> None:
    production_id = ProductionService(db_session).create_production(
        ProductionCreate(name="Rule Model")
    ).id
    service = RuleService(db_session)
    row = service.create_rule(
        RuleCreate(
            production_id=production_id,
            name="Mood warm",
            conditions=[{"type": "mood", "mood": "warm"}],
            actions=[{"type": "select_from_group", "group": "atmosphere"}],
            cooldown_seconds=12.5,
        )
    )
    loaded = db_session.get(Rule, row.id)
    assert loaded is not None
    assert loaded.production_id == production_id
    assert loaded.conditions == [{"type": "mood", "mood": "warm"}]
    assert loaded.actions == [{"type": "select_from_group", "group": "atmosphere"}]
    assert loaded.cooldown_seconds == 12.5
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
