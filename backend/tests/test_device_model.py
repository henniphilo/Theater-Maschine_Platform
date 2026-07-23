from __future__ import annotations

from datetime import datetime

from app.models.device import DEFAULT_ADAPTER_TYPE, Device
from app.models.production import Production
from app.services.device_secrets import pack_for_storage, unpack_from_storage


def _seed_production(db_session) -> Production:
    row = Production(name="Device Show", slug="device-show")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_device_model_defaults_to_dry_run(db_session) -> None:
    production = _seed_production(db_session)
    public, sealed = pack_for_storage({"host": "10.0.0.1", "port": 7000, "notes": "probe"})
    row = Device(
        production_id=production.id,
        name="Probe OSC",
        configuration=public,
        configuration_sealed=sealed,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id
    assert len(row.id) == 36
    assert row.adapter_type == DEFAULT_ADAPTER_TYPE
    assert row.adapter_type == "dry_run"
    assert row.enabled is True
    assert "host" not in row.configuration
    assert row.configuration.get("notes") == "probe"
    full = unpack_from_storage(
        configuration=row.configuration,
        configuration_sealed=row.configuration_sealed,
    )
    assert full["host"] == "10.0.0.1"
    assert full["port"] == 7000
    assert isinstance(row.created_at, datetime)


def test_device_production_id_optional(db_session) -> None:
    public, sealed = pack_for_storage({})
    row = Device(
        name="Global Dry Run",
        adapter_type="dry_run",
        configuration=public,
        configuration_sealed=sealed,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.production_id is None
