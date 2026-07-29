from __future__ import annotations

from app.director.cues.safety import get_safety_state
from app.director.pipeline import get_director_pipeline
from app.schemas.device import DeviceCreate
from app.schemas.production import ProductionCreate
from app.services import active_production as active_production_store
from app.services.device_service import DeviceService
from app.services.director_production_context import (
    active_production_status,
    emergency_stop_active_production_devices,
)
from app.services.production_service import ProductionService


def test_active_production_status(db_session, active_store) -> None:
    empty = active_production_status(db_session)
    assert empty["active_production_id"] is None

    prod = ProductionService(db_session).create_production(ProductionCreate(name="Dir Show"))
    ProductionService(db_session).set_active(prod.id)
    status = active_production_status(db_session)
    assert status["active_production_id"] == prod.id
    assert status["active_production_name"] == "Dir Show"


def test_emergency_stop_calls_enabled_devices(db_session, active_store) -> None:
    prod = ProductionService(db_session).create_production(ProductionCreate(name="E-Stop"))
    active_production_store.set_active_production_id(prod.id)
    DeviceService(db_session).create_device(
        DeviceCreate(
            production_id=prod.id,
            name="Out",
            adapter_type="dry_run",
            enabled=True,
            configuration={},
        )
    )
    DeviceService(db_session).create_device(
        DeviceCreate(
            production_id=prod.id,
            name="Off",
            adapter_type="dry_run",
            enabled=False,
            configuration={},
        )
    )
    results = emergency_stop_active_production_devices(db_session)
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["dry_run"] is True


def test_pipeline_emergency_includes_production_devices(monkeypatch) -> None:
    calls: list[str] = []

    def fake_stop(db=None):
        calls.append("devices")
        return [{"device_id": "x", "ok": True}]

    import app.services.director_production_context as ctx_mod

    monkeypatch.setattr(ctx_mod, "emergency_stop_active_production_devices", fake_stop)

    pipeline = get_director_pipeline()
    monkeypatch.setattr(pipeline.sound, "stop_all", lambda dry_run=True: None)
    monkeypatch.setattr(pipeline.lighting, "blackout", lambda dry_run=True: None)
    monkeypatch.setattr(pipeline.touchdesigner, "blackout", lambda: None)

    safety = get_safety_state()
    safety.clear_emergency_stop()
    try:
        pipeline.emergency_stop()
        assert safety.emergency_stop_active is True
        assert calls == ["devices"]
    finally:
        safety.clear_emergency_stop()


def test_director_status_includes_active_production(api_client) -> None:
    production = api_client.post("/api/v1/productions", json={"name": "Status Prod"}).json()
    api_client.put("/api/v1/productions/active", json={"production_id": production["id"]})
    status = api_client.get("/api/v1/director/status")
    assert status.status_code == 200
    body = status.json()
    assert body["active_production_id"] == production["id"]
    assert body["active_production_name"] == "Status Prod"
