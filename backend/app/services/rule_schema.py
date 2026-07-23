"""Validated condition/action structures for production Rules (MVP)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

ConditionType = Literal[
    "text_contains",
    "tag",
    "mood",
    "intensity_min",
    "intensity_max",
    "previous_cue",
    "manual",
]

ActionType = Literal[
    "execute_cue",
    "select_from_group",
    "select_random_by_tags",
    "execute_delayed",
]

CONDITION_TYPES = frozenset(
    (
        "text_contains",
        "tag",
        "mood",
        "intensity_min",
        "intensity_max",
        "previous_cue",
        "manual",
    )
)

ACTION_TYPES = frozenset(
    (
        "execute_cue",
        "select_from_group",
        "select_random_by_tags",
        "execute_delayed",
    )
)


def _strip_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned


class RuleCondition(BaseModel):
    """Single AND-ed condition (all conditions on a rule must match)."""

    type: ConditionType
    term: str | None = None
    tag: str | None = None
    mood: str | None = None
    value: float | None = None
    cue_id: str | None = None
    activation_key: str | None = None

    @field_validator("term", "tag", "mood", "cue_id", "activation_key")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @model_validator(mode="after")
    def validate_fields_for_type(self) -> RuleCondition:
        t = self.type
        if t == "text_contains":
            if not self.term:
                raise ValueError("text_contains requires term")
        elif t == "tag":
            if not self.tag:
                raise ValueError("tag requires tag")
        elif t == "mood":
            if not self.mood:
                raise ValueError("mood requires mood")
        elif t == "intensity_min":
            if self.value is None:
                raise ValueError("intensity_min requires value")
            if not 0.0 <= self.value <= 1.0:
                raise ValueError("intensity_min value must be between 0 and 1")
        elif t == "intensity_max":
            if self.value is None:
                raise ValueError("intensity_max requires value")
            if not 0.0 <= self.value <= 1.0:
                raise ValueError("intensity_max value must be between 0 and 1")
        elif t == "previous_cue":
            if not self.cue_id:
                raise ValueError("previous_cue requires cue_id")
        elif t == "manual":
            if not self.activation_key:
                raise ValueError("manual requires activation_key")
        return self

    def to_storage(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        return data


class RuleAction(BaseModel):
    """Single action produced when a rule matches."""

    type: ActionType
    cue_id: str | None = None
    group: str | None = None
    tags: list[str] | None = None
    delay_seconds: float | None = None

    @field_validator("cue_id", "group")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [_strip_required(t) for t in value]
        if not cleaned:
            raise ValueError("tags must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_fields_for_type(self) -> RuleAction:
        t = self.type
        if t == "execute_cue":
            if not self.cue_id:
                raise ValueError("execute_cue requires cue_id")
        elif t == "select_from_group":
            if not self.group:
                raise ValueError("select_from_group requires group")
        elif t == "select_random_by_tags":
            if not self.tags:
                raise ValueError("select_random_by_tags requires tags")
        elif t == "execute_delayed":
            if not self.cue_id:
                raise ValueError("execute_delayed requires cue_id")
            if self.delay_seconds is None:
                raise ValueError("execute_delayed requires delay_seconds")
            if self.delay_seconds < 0:
                raise ValueError("delay_seconds must be >= 0")
        return self

    def to_storage(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def validate_conditions(raw: list[dict[str, Any]] | list[RuleCondition]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("conditions must be a list")
    if len(raw) == 0:
        raise ValueError("conditions must not be empty")
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, RuleCondition):
            out.append(item.to_storage())
        else:
            out.append(RuleCondition.model_validate(item).to_storage())
    return out


def validate_actions(raw: list[dict[str, Any]] | list[RuleAction]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("actions must be a list")
    if len(raw) == 0:
        raise ValueError("actions must not be empty")
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, RuleAction):
            out.append(item.to_storage())
        else:
            out.append(RuleAction.model_validate(item).to_storage())
    return out


def parse_conditions(raw: list[dict[str, Any]]) -> list[RuleCondition]:
    return [RuleCondition.model_validate(item) for item in validate_conditions(raw)]


def parse_actions(raw: list[dict[str, Any]]) -> list[RuleAction]:
    return [RuleAction.model_validate(item) for item in validate_actions(raw)]
