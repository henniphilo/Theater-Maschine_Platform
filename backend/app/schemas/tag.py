from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned


class TagCreate(BaseModel):
    production_id: str = Field(..., min_length=1, max_length=36)
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("production_id", "name")
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        return _strip_required(value)


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    production_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class AssetTagAttach(BaseModel):
    """Attach an existing tag or create-by-name within the asset's production."""

    tag_id: str | None = Field(default=None, min_length=1, max_length=36)
    name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("tag_id", "name")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @model_validator(mode="after")
    def exactly_one_of_tag_id_or_name(self) -> AssetTagAttach:
        if (self.tag_id is None) == (self.name is None):
            raise ValueError("exactly one of tag_id or name is required")
        return self
