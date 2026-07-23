from __future__ import annotations

import json

from app.schemas.production import ProductionCreate, ProductionUpdate
from app.services.production_service import (
    ProductionConflictError,
    ProductionService,
    ProductionValidationError,
    slugify,
)
def test_slugify_basic() -> None:
    assert slugify("Unter Tieren!") == "unter-tieren"
    assert slugify("  Äpfel & Birnen  ") == "apfel-birnen"


def test_create_and_list(db_session, active_store) -> None:
    service = ProductionService(db_session)
    created = service.create_production(ProductionCreate(name="Show A", description="d"))
    assert created.status == "draft"
    assert created.slug == "show-a"
    rows = service.list_productions()
    assert len(rows) == 1
    assert rows[0].id == created.id


def test_unique_slug_auto_suffix(db_session, active_store) -> None:
    service = ProductionService(db_session)
    a = service.create_production(ProductionCreate(name="Show", slug="show"))
    b = service.create_production(ProductionCreate(name="Show 2", slug="show"))
    assert a.slug == "show"
    assert b.slug == "show-2"


def test_update_and_archive(db_session, active_store) -> None:
    service = ProductionService(db_session)
    row = service.create_production(ProductionCreate(name="Old"))
    updated = service.update_production(row.id, ProductionUpdate(name="New", description="x"))
    assert updated.name == "New"
    assert updated.description == "x"

    archived = service.archive_production(row.id)
    assert archived.status == "archived"
    assert archived.archived_at is not None


def test_set_active_rejects_archived(db_session, active_store) -> None:
    service = ProductionService(db_session)
    row = service.create_production(ProductionCreate(name="Gone"))
    service.archive_production(row.id)
    try:
        service.set_active(row.id)
        raised = False
    except ProductionValidationError:
        raised = True
    assert raised is True


def test_set_active_persists_json(db_session, active_store) -> None:
    service = ProductionService(db_session)
    row = service.create_production(ProductionCreate(name="Live"))
    production_id, active = service.set_active(row.id)
    assert production_id == row.id
    assert active is not None
    assert active.status == "active_eligible"

    path = active_store / "active_production.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["production_id"] == row.id

    got_id, got = service.get_active()
    assert got_id == row.id
    assert got is not None


def test_archive_clears_active(db_session, active_store) -> None:
    service = ProductionService(db_session)
    row = service.create_production(ProductionCreate(name="Live"))
    service.set_active(row.id)
    service.archive_production(row.id)
    production_id, active = service.get_active()
    assert production_id is None
    assert active is None


def test_slug_conflict_on_update(db_session, active_store) -> None:
    service = ProductionService(db_session)
    a = service.create_production(ProductionCreate(name="A", slug="alpha"))
    b = service.create_production(ProductionCreate(name="B", slug="beta"))
    try:
        service.update_production(b.id, ProductionUpdate(slug=a.slug))
        raised = False
    except ProductionConflictError:
        raised = True
    assert raised is True
