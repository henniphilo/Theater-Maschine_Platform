from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.rule_schema import validate_actions, validate_conditions


def _strip_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned


class RuleCreate(BaseModel):
    production_id: str = Field(..., min_length=1, max_length=36)
    name: str = Field(..., min_length=1, max_length=200)
    enabled: bool = True
    priority: int = Field(default=0, ge=-1000, le=1000)
    conditions: list[dict[str, Any]] = Field(..., min_length=1)
    actions: list[dict[str, Any]] = Field(..., min_length=1)
    cooldown_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)

    @field_validator("production_id", "name")
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        return _strip_required(value)

    @model_validator(mode="after")
    def validate_structures(self) -> RuleCreate:
        self.conditions = validate_conditions(self.conditions)
        self.actions = validate_actions(self.actions)
        return self


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    conditions: list[dict[str, Any]] | None = None
    actions: list[dict[str, Any]] | None = None
    cooldown_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)
    clear_cooldown_seconds: bool = False

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @model_validator(mode="after")
    def validate_structures(self) -> RuleUpdate:
        if self.conditions is not None:
            self.conditions = validate_conditions(self.conditions)
        if self.actions is not None:
            self.actions = validate_actions(self.actions)
        return self


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    production_id: str
    name: str
    enabled: bool
    priority: int
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    cooldown_seconds: float | None
    created_at: datetime
    updated_at: datetime


class RuleEvaluateRequest(BaseModel):
    """Dry evaluation of production rules (and optionally legacy JSON)."""

    text: str = ""
    tags: list[str] = Field(default_factory=list)
    mood: str | None = None
    intensity: float = Field(default=0.0, ge=0.0, le=1.0)
    previous_cue_id: str | None = None
    manual_keys: list[str] = Field(default_factory=list)
    now_seconds: float = Field(default=0.0, ge=0.0)
    include_legacy_json: bool = False
    stop_after_first_match: bool = False
    available_cues: list[dict[str, Any]] = Field(default_factory=list)


class RuleEvaluateResponse(BaseModel):
    production_id: str
    matches: list[dict[str, Any]] = Field(default_factory=list)
    skipped_cooldown: list[str] = Field(default_factory=list)
    skipped_disabled: list[str] = Field(default_factory=list)
    skipped_conditions: list[str] = Field(default_factory=list)


class LegacyRuleSummary(BaseModel):
    """Read-only view of a CanonicalRule compiled from dramaturgy_rules.json."""

    id: str
    name: str
    enabled: bool
    priority: int
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    cooldown_seconds: float | None
    source: str = "json"
    meta: dict[str, str] = Field(default_factory=dict)
