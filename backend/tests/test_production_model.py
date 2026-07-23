from __future__ import annotations

from datetime import datetime, timezone

from app.models.production import Production, ProductionStatus
def test_production_model_defaults(db_session) -> None:
    row = Production(name="Probe", slug="probe", description="Test")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id
    assert len(row.id) == 36
    assert row.name == "Probe"
    assert row.slug == "probe"
    assert row.description == "Test"
    assert row.status == ProductionStatus.DRAFT.value
    assert row.archived_at is None
    assert isinstance(row.created_at, datetime)
    assert isinstance(row.updated_at, datetime)


def test_production_slug_unique(db_session) -> None:
    db_session.add(Production(name="A", slug="same"))
    db_session.commit()
    db_session.add(Production(name="B", slug="same"))
    try:
        db_session.commit()
        raised = False
    except Exception:
        db_session.rollback()
        raised = True
    assert raised is True


def test_production_archived_at_optional(db_session) -> None:
    now = datetime.now(timezone.utc)
    row = Production(
        name="Archiv",
        slug="archiv",
        status=ProductionStatus.ARCHIVED.value,
        archived_at=now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.archived_at is not None
