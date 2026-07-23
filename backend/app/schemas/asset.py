from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.tag import TagRead

AssetTypeLiteral = Literal["video", "audio", "image", "text", "document", "data", "other"]


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


class AssetCreate(BaseModel):
    """Internal/service payload to register asset metadata (no multipart upload)."""

    production_id: str = Field(..., min_length=1, max_length=36)
    name: str = Field(..., min_length=1, max_length=200)
    type: AssetTypeLiteral
    original_filename: str = Field(..., min_length=1, max_length=500)
    storage_key: str = Field(..., min_length=1, max_length=512)
    mime_type: str = Field(..., min_length=1, max_length=200)
    size_bytes: int = Field(..., ge=0)
    checksum: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "original_filename", "storage_key", "mime_type", "checksum")
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("production_id")
    @classmethod
    def strip_production_id(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AssetUpdate(BaseModel):
    """Mutable metadata only — file-bound fields stay immutable in this milestone."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: AssetTypeLiteral | None = None
    description: str | None = Field(default=None, max_length=5000)
    metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    production_id: str
    name: str
    type: AssetTypeLiteral
    original_filename: str
    storage_key: str
    mime_type: str
    size_bytes: int
    checksum: str
    description: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[TagRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def map_orm_metadata(cls, data: Any) -> Any:
        if hasattr(data, "metadata_json"):
            tags = getattr(data, "tags", None) or []
            return {
                "id": data.id,
                "production_id": data.production_id,
                "name": data.name,
                "type": data.type,
                "original_filename": data.original_filename,
                "storage_key": data.storage_key,
                "mime_type": data.mime_type,
                "size_bytes": data.size_bytes,
                "checksum": data.checksum,
                "description": data.description,
                "metadata": data.metadata_json if data.metadata_json is not None else {},
                "tags": tags,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        if isinstance(data, dict) and "metadata_json" in data and "metadata" not in data:
            mapped = dict(data)
            mapped["metadata"] = mapped.pop("metadata_json") or {}
            return mapped
        return data


class AssetPreview(BaseModel):
    """Lightweight preview metadata for suitable asset types."""

    asset_id: str
    production_id: str
    mime_type: str
    kind: Literal["image", "audio", "video", "text", "json", "none"]
    preview_available: bool
    text_excerpt: str | None = None
    size_bytes: int
    original_filename: str
