"""Schemas for Burgtheater admin import API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BurgtheaterImportRequest(BaseModel):
    """Admin import request. Defaults to dry-run analysis."""

    dry_run: bool = True
    include_hardware_addresses: bool = False
    hardware_address_overlay: dict[str, dict[str, Any]] = Field(default_factory=dict)
    copy_media_into_storage: bool = True
    # Optional path overrides (absolute or repo-relative). Empty = repo defaults.
    data_dir: str | None = None
    media_dir: str | None = None
    repo_root: str | None = None


class BurgtheaterImportResponse(BaseModel):
    dry_run: bool
    production_id: str | None
    production_slug: str
    production_name: str
    source_root: str
    warnings: list[dict[str, Any]]
    counts_by_kind: dict[str, dict[str, int]]
    changes: list[dict[str, Any]]
    sources_seen: list[str]
    missing_media: list[str]
    summary: dict[str, Any]
