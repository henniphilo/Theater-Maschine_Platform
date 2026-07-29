"""Active-production helpers for Director status and emergency stop."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.adapters import UnknownAdapterTypeError, build_adapter_for_device
from app.services import active_production as active_production_store
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)


def active_production_status(db: Session | None = None) -> dict[str, Any]:
    """Return active production fields for DirectorStatusResponse.

    Reads the file-backed active id first. Name/slug are best-effort from DB and
    must not clear the active selection when the row is missing (e.g. test SQLite
    vs opportunistic Postgres SessionLocal).
    """
    production_id = active_production_store.get_active_production_id()
    if not production_id:
        return {
            "active_production_id": None,
            "active_production_name": None,
            "active_production_slug": None,
        }

    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal

        db = SessionLocal()
    assert db is not None
    try:
        from app.models.production import Production, ProductionStatus

        row = db.get(Production, production_id)
        if row is None or row.status == ProductionStatus.ARCHIVED.value:
            return {
                "active_production_id": production_id,
                "active_production_name": None,
                "active_production_slug": None,
            }
        return {
            "active_production_id": production_id,
            "active_production_name": row.name,
            "active_production_slug": row.slug,
        }
    except Exception:
        logger.debug("active production name lookup unavailable", exc_info=True)
        return {
            "active_production_id": production_id,
            "active_production_name": None,
            "active_production_slug": None,
        }
    finally:
        if owns_session:
            db.close()


def emergency_stop_active_production_devices(db: Session | None = None) -> list[dict[str, Any]]:
    """Best-effort adapter.emergency_stop for enabled devices of the active production.

    Failures are logged and collected; new cue execution remains blocked via SafetyState.
    """
    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal

        db = SessionLocal()
    assert db is not None
    results: list[dict[str, Any]] = []
    try:
        production_id = active_production_store.get_active_production_id()
        if not production_id:
            return results
        devices = DeviceService(db).list_devices(
            production_id=production_id,
            enabled=True,
            include_global=True,
        )
        for device in devices:
            entry: dict[str, Any] = {
                "device_id": device.id,
                "name": device.name,
                "adapter_type": device.adapter_type,
            }
            try:
                adapter = build_adapter_for_device(device)
                result = adapter.emergency_stop()
                entry["ok"] = result.ok
                entry["message"] = result.message
                entry["dry_run"] = result.dry_run
            except UnknownAdapterTypeError as exc:
                entry["ok"] = False
                entry["message"] = str(exc)
            except Exception as exc:  # noqa: BLE001 — best-effort emergency path
                logger.exception("device emergency_stop failed device_id=%s", device.id)
                entry["ok"] = False
                entry["message"] = str(exc)
            results.append(entry)
        return results
    finally:
        if owns_session:
            db.close()
