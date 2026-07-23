from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.device import ADAPTER_TYPES, DEFAULT_ADAPTER_TYPE

AdapterTypeLiteral = Literal["dry_run", "osc", "midi", "pixera", "eos_tcp"]


def _strip_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class DeviceCreate(BaseModel):
    production_id: str | None = Field(default=None, max_length=36)
    name: str = Field(..., min_length=1, max_length=200)
    # Dry-run is the safe default for newly created devices.
    adapter_type: AdapterTypeLiteral = DEFAULT_ADAPTER_TYPE  # type: ignore[assignment]
    enabled: bool = True
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("production_id")
    @classmethod
    def strip_production_id(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_type(cls, value: str) -> str:
        if value not in ADAPTER_TYPES:
            raise ValueError(f"invalid adapter_type: {value}")
        return value

    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("configuration must be an object")
        return dict(value)


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    adapter_type: AdapterTypeLiteral | None = None
    enabled: bool | None = None
    configuration: dict[str, Any] | None = None
    clear_production_id: bool = False
    production_id: str | None = Field(default=None, max_length=36)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @field_validator("production_id")
    @classmethod
    def strip_production_id(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in ADAPTER_TYPES:
            raise ValueError(f"invalid adapter_type: {value}")
        return value

    @model_validator(mode="after")
    def configuration_is_object(self) -> DeviceUpdate:
        if self.configuration is not None and not isinstance(self.configuration, dict):
            raise ValueError("configuration must be an object")
        return self


class DeviceRead(BaseModel):
    """API read model — sensitive configuration values are never included."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    production_id: str | None
    name: str
    adapter_type: AdapterTypeLiteral
    enabled: bool
    # Public-only keys (hosts/ports/secrets omitted).
    configuration: dict[str, Any] = Field(default_factory=dict)
    configuration_keys: list[str] = Field(default_factory=list)
    has_sensitive_configuration: bool = False
    created_at: datetime
    updated_at: datetime


class DeviceConnectionTestResult(BaseModel):
    device_id: str
    adapter_type: AdapterTypeLiteral
    ok: bool
    message: str
    dry_run: bool
    details: dict[str, Any] = Field(default_factory=dict)


class DeviceHealthResult(BaseModel):
    device_id: str
    adapter_type: AdapterTypeLiteral
    status: str
    message: str
    connected: bool
    details: dict[str, Any] = Field(default_factory=dict)
