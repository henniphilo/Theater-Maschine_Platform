"""Resolve visual output slots for the active Production.

Legacy Burgtheater IDs (adam/eva/rz21/led) remain the fallback when no active
Production device exposes ``configuration.output_slots``. New productions should
configure slots on a pixera/visual Device — see Burgtheater import templates.

M8 follow-ups (not in this milestone): rename aidebatte package, Compose Dry-Run
defaults, Redis purpose decision.
"""

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy.orm import Session

from app.services import active_production as active_production_store
from app.services.device_secrets import unpack_from_storage

logger = logging.getLogger(__name__)

# Legacy venue fallback — used only when no production device configures slots.
LEGACY_OUTPUT_SLOTS: tuple[str, ...] = ("adam", "eva", "rz21", "led")
LEGACY_ATMOSPHERE_FREE_SLOT = "rz21"


def normalize_output_slots(raw: Sequence[object] | None) -> tuple[str, ...]:
    slots: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        slots.append(value)
    return tuple(slots)


def slots_from_device_configuration(configuration: dict | None) -> tuple[str, ...]:
    if not configuration:
        return ()
    raw = configuration.get("output_slots")
    if raw is None and isinstance(configuration.get("outputs"), list):
        # Accept either list of ids or list of {id: ...} objects.
        outputs = configuration.get("outputs") or []
        ids: list[object] = []
        for item in outputs:
            if isinstance(item, dict):
                ids.append(item.get("id") or item.get("output_id"))
            else:
                ids.append(item)
        raw = ids
    return normalize_output_slots(raw if isinstance(raw, (list, tuple)) else None)


def atmosphere_free_slots_from_configuration(configuration: dict | None) -> frozenset[str]:
    if not configuration:
        return frozenset()
    raw = configuration.get("atmosphere_free_slots")
    if raw is None:
        return frozenset()
    return frozenset(normalize_output_slots(raw if isinstance(raw, (list, tuple)) else None))


def resolve_output_slots(db: Session | None = None) -> tuple[str, ...]:
    """Return output slot ids for the active Production, or legacy defaults."""
    production_id = active_production_store.get_active_production_id()
    if not production_id:
        return LEGACY_OUTPUT_SLOTS

    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal

        db = SessionLocal()
    assert db is not None
    try:
        from app.models.device import Device
        from sqlalchemy import select

        rows = list(
            db.scalars(
                select(Device).where(
                    (Device.production_id == production_id) | (Device.production_id.is_(None))
                )
            ).all()
        )
        for row in rows:
            config = unpack_from_storage(
                configuration=row.configuration,
                configuration_sealed=row.configuration_sealed,
            )
            slots = slots_from_device_configuration(config)
            if slots:
                return slots
        return LEGACY_OUTPUT_SLOTS
    except Exception:
        logger.debug("output slot resolve failed; using legacy", exc_info=True)
        return LEGACY_OUTPUT_SLOTS
    finally:
        if owns_session:
            db.close()


def resolve_atmosphere_free_slots(db: Session | None = None) -> frozenset[str]:
    """Slots that stay unlocked for atmosphere (legacy: rz21)."""
    production_id = active_production_store.get_active_production_id()
    if not production_id:
        return frozenset({LEGACY_ATMOSPHERE_FREE_SLOT})

    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal

        db = SessionLocal()
    assert db is not None
    try:
        from app.models.device import Device
        from sqlalchemy import select

        rows = list(
            db.scalars(
                select(Device).where(
                    (Device.production_id == production_id) | (Device.production_id.is_(None))
                )
            ).all()
        )
        for row in rows:
            config = unpack_from_storage(
                configuration=row.configuration,
                configuration_sealed=row.configuration_sealed,
            )
            configured = atmosphere_free_slots_from_configuration(config)
            if configured:
                return configured
            # If device defines output_slots but no free-list, keep legacy rz21 only
            # when that id is present in the slot list.
            slots = slots_from_device_configuration(config)
            if slots:
                if LEGACY_ATMOSPHERE_FREE_SLOT in slots:
                    return frozenset({LEGACY_ATMOSPHERE_FREE_SLOT})
                return frozenset()
        return frozenset({LEGACY_ATMOSPHERE_FREE_SLOT})
    except Exception:
        logger.debug("atmosphere-free slot resolve failed; using legacy", exc_info=True)
        return frozenset({LEGACY_ATMOSPHERE_FREE_SLOT})
    finally:
        if owns_session:
            db.close()


def default_preview_projector(db: Session | None = None) -> str:
    slots = resolve_output_slots(db)
    free = resolve_atmosphere_free_slots(db)
    for slot in slots:
        if slot in free:
            return slot
    return slots[0] if slots else LEGACY_ATMOSPHERE_FREE_SLOT
