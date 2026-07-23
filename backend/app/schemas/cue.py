from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.cue_parameters import (
    validate_cue_action,
    validate_cue_parameters,
    validate_cue_type_requirements,
)

CueTypeLiteral = Literal["video", "audio", "light", "osc", "midi", "text", "wait"]


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


class CueCreate(BaseModel):
    production_id: str = Field(..., min_length=1, max_length=36)
    name: str = Field(..., min_length=1, max_length=200)
    cue_type: CueTypeLiteral
    action: str = Field(..., min_length=1, max_length=64)
    asset_id: str | None = Field(default=None, max_length=36)
    device_id: str | None = Field(default=None, max_length=36)
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = Field(default=0, ge=-1000, le=1000)
    cooldown_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)

    @field_validator("production_id", "name", "action")
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("asset_id", "device_id")
    @classmethod
    def strip_optional_ids(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def validate_typed_fields(self) -> CueCreate:
        action = validate_cue_action(self.cue_type, self.action)
        params = validate_cue_parameters(self.cue_type, self.parameters)
        validate_cue_type_requirements(
            cue_type=self.cue_type,
            action=action,
            parameters=params,
            asset_id=self.asset_id,
        )
        self.action = action
        self.parameters = params
        return self


class CueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    cue_type: CueTypeLiteral | None = None
    action: str | None = Field(default=None, min_length=1, max_length=64)
    asset_id: str | None = Field(default=None, max_length=36)
    device_id: str | None = Field(default=None, max_length=36)
    parameters: dict[str, Any] | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    cooldown_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)
    clear_asset_id: bool = False
    clear_device_id: bool = False
    clear_cooldown_seconds: bool = False

    @field_validator("name", "action")
    @classmethod
    def strip_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @field_validator("asset_id", "device_id")
    @classmethod
    def strip_optional_ids(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    production_id: str
    name: str
    cue_type: CueTypeLiteral
    asset_id: str | None
    device_id: str | None
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    priority: int
    cooldown_seconds: float | None
    created_at: datetime
    updated_at: datetime


class CueExecuteRequest(BaseModel):
    """UI/API may only request dry-run in this milestone."""

    dry_run: bool = True


class CueExecutionResult(BaseModel):
    cue_id: str
    production_id: str
    dry_run: bool
    status: Literal["planned", "skipped", "rejected"]
    message: str
    planned: dict[str, Any] = Field(default_factory=dict)


class LegacyCueSummary(BaseModel):
    """Read-only view of a legacy JSON/CSV catalog entry (not a DB Cue)."""

    source: Literal["video_cues", "sound_cues"]
    catalog_id: str
    label: str
    cue_type: CueTypeLiteral
    suggested_action: str
    details: dict[str, Any] = Field(default_factory=dict)
