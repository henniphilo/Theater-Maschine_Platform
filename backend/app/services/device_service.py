"""CRUD and adapter operations for Devices."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import UnknownAdapterTypeError, build_adapter_for_device
from app.models.device import ADAPTER_TYPES, DEFAULT_ADAPTER_TYPE, Device
from app.models.production import Production
from app.schemas.device import (
    DeviceConnectionTestResult,
    DeviceCreate,
    DeviceHealthResult,
    DeviceRead,
    DeviceUpdate,
)
from app.services.device_secrets import (
    configuration_key_names,
    is_sensitive_key,
    pack_for_storage,
    redact_configuration,
    unpack_from_storage,
)


class DeviceError(Exception):
    """Base service error."""


class DeviceNotFoundError(DeviceError):
    pass


class DeviceValidationError(DeviceError):
    pass


class DeviceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_devices(
        self,
        *,
        production_id: str | None = None,
        adapter_type: str | None = None,
        enabled: bool | None = None,
        include_global: bool = True,
    ) -> list[Device]:
        if adapter_type is not None and adapter_type not in ADAPTER_TYPES:
            raise DeviceValidationError(f"invalid adapter_type: {adapter_type}")

        stmt = select(Device).order_by(Device.created_at.desc())
        if production_id is not None:
            if include_global:
                stmt = stmt.where(
                    (Device.production_id == production_id) | (Device.production_id.is_(None))
                )
            else:
                stmt = stmt.where(Device.production_id == production_id)
        if adapter_type is not None:
            stmt = stmt.where(Device.adapter_type == adapter_type)
        if enabled is not None:
            stmt = stmt.where(Device.enabled.is_(enabled))
        return list(self.db.scalars(stmt).all())

    def get_device(self, device_id: str, *, production_id: str | None = None) -> Device:
        row = self.db.get(Device, device_id)
        if row is None:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        if production_id is not None:
            if row.production_id is not None and row.production_id != production_id:
                raise DeviceNotFoundError(f"Device {device_id} not found")
        return row

    def create_device(self, payload: DeviceCreate) -> Device:
        adapter_type = payload.adapter_type or DEFAULT_ADAPTER_TYPE
        if adapter_type not in ADAPTER_TYPES:
            raise DeviceValidationError(f"invalid adapter_type: {adapter_type}")
        if payload.production_id is not None:
            if self.db.get(Production, payload.production_id) is None:
                raise DeviceValidationError(f"production {payload.production_id} not found")

        public, sealed = pack_for_storage(dict(payload.configuration))
        row = Device(
            production_id=payload.production_id,
            name=payload.name,
            adapter_type=adapter_type,
            enabled=payload.enabled,
            configuration=public,
            configuration_sealed=sealed,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_device(self, device_id: str, payload: DeviceUpdate) -> Device:
        row = self.get_device(device_id)
        data = payload.model_dump(exclude_unset=True)
        clear_production = bool(data.pop("clear_production_id", False))

        if "name" in data and data["name"] is not None:
            row.name = data["name"]
        if "adapter_type" in data and data["adapter_type"] is not None:
            if data["adapter_type"] not in ADAPTER_TYPES:
                raise DeviceValidationError(f"invalid adapter_type: {data['adapter_type']}")
            row.adapter_type = data["adapter_type"]
        if "enabled" in data and data["enabled"] is not None:
            row.enabled = data["enabled"]

        if clear_production:
            row.production_id = None
        elif "production_id" in data:
            production_id = data["production_id"]
            if production_id is not None and self.db.get(Production, production_id) is None:
                raise DeviceValidationError(f"production {production_id} not found")
            row.production_id = production_id

        if "configuration" in data and data["configuration"] is not None:
            public, sealed = pack_for_storage(dict(data["configuration"]))
            row.configuration = public
            row.configuration_sealed = sealed

        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_device(self, device_id: str, *, production_id: str | None = None) -> None:
        row = self.get_device(device_id, production_id=production_id)
        self.db.delete(row)
        self.db.commit()

    def to_read(self, row: Device) -> DeviceRead:
        full = unpack_from_storage(
            configuration=row.configuration,
            configuration_sealed=row.configuration_sealed,
        )
        public = redact_configuration(row.configuration)
        keys = configuration_key_names(full)
        has_sensitive = any(is_sensitive_key(k) for k in keys)
        return DeviceRead(
            id=row.id,
            production_id=row.production_id,
            name=row.name,
            adapter_type=row.adapter_type,  # type: ignore[arg-type]
            enabled=row.enabled,
            configuration=public,
            configuration_keys=keys,
            has_sensitive_configuration=has_sensitive,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def full_configuration(self, row: Device) -> dict[str, Any]:
        """Internal use only — never return from API routes."""
        return unpack_from_storage(
            configuration=row.configuration,
            configuration_sealed=row.configuration_sealed,
        )

    def test_connection(
        self,
        device_id: str,
        *,
        production_id: str | None = None,
    ) -> DeviceConnectionTestResult:
        row = self.get_device(device_id, production_id=production_id)
        try:
            adapter = build_adapter_for_device(row)
        except UnknownAdapterTypeError as exc:
            raise DeviceValidationError(str(exc)) from exc
        result = adapter.test_connection()
        # Strip any accidental sensitive values from adapter details.
        safe_details = redact_configuration(result.details)
        return DeviceConnectionTestResult(
            device_id=row.id,
            adapter_type=row.adapter_type,  # type: ignore[arg-type]
            ok=result.ok,
            message=result.message,
            dry_run=result.dry_run,
            details=safe_details,
        )

    def health(
        self,
        device_id: str,
        *,
        production_id: str | None = None,
    ) -> DeviceHealthResult:
        row = self.get_device(device_id, production_id=production_id)
        try:
            adapter = build_adapter_for_device(row)
        except UnknownAdapterTypeError as exc:
            raise DeviceValidationError(str(exc)) from exc
        status = adapter.health_status()
        return DeviceHealthResult(
            device_id=row.id,
            adapter_type=row.adapter_type,  # type: ignore[arg-type]
            status=status.status.value,
            message=status.message,
            connected=status.connected,
            details=redact_configuration(status.details),
        )
