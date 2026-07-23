from __future__ import annotations

from app.schemas.device import DeviceCreate
from app.services.device_service import DeviceService


def _create_production(db_session):
    from app.models.production import Production

    row = Production(name="Device Service Show", slug="device-service-show")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_device_service_create_defaults_dry_run_and_redacts(db_session) -> None:
    production = _create_production(db_session)
    service = DeviceService(db_session)
    row = service.create_device(
        DeviceCreate(
            production_id=production.id,
            name="Safe Device",
            configuration={"host": "192.168.1.50", "port": 7000, "notes": "td"},
        )
    )
    assert row.adapter_type == "dry_run"
    read = service.to_read(row)
    assert read.configuration == {"notes": "td"}
    assert "host" not in read.configuration
    assert "host" in read.configuration_keys
    assert read.has_sensitive_configuration is True

    full = service.full_configuration(row)
    assert full["host"] == "192.168.1.50"


def test_device_service_test_connection(db_session) -> None:
    production = _create_production(db_session)
    service = DeviceService(db_session)
    row = service.create_device(
        DeviceCreate(
            production_id=production.id,
            name="Dry",
            adapter_type="dry_run",
        )
    )
    result = service.test_connection(row.id, production_id=production.id)
    assert result.ok is True
    assert result.dry_run is True
    assert "host" not in result.details
