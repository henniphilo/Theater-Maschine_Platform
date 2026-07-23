"""CRUD service for domain Cues."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cue import CUE_TYPES, Cue
from app.models.production import Production
from app.schemas.cue import CueCreate, CueUpdate
from app.services.cue_parameters import (
    validate_cue_action,
    validate_cue_parameters,
    validate_cue_type_requirements,
)


class CueError(Exception):
    """Base service error."""


class CueNotFoundError(CueError):
    pass


class CueValidationError(CueError):
    pass


class CueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_cues(
        self,
        *,
        production_id: str | None = None,
        cue_type: str | None = None,
        enabled: bool | None = None,
    ) -> list[Cue]:
        if cue_type is not None and cue_type not in CUE_TYPES:
            raise CueValidationError(f"invalid cue_type: {cue_type}")

        stmt = select(Cue).order_by(Cue.priority.desc(), Cue.created_at.desc())
        if production_id is not None:
            stmt = stmt.where(Cue.production_id == production_id)
        if cue_type is not None:
            stmt = stmt.where(Cue.cue_type == cue_type)
        if enabled is not None:
            stmt = stmt.where(Cue.enabled.is_(enabled))
        return list(self.db.scalars(stmt).all())

    def get_cue(self, cue_id: str, *, production_id: str | None = None) -> Cue:
        row = self.db.get(Cue, cue_id)
        if row is None:
            raise CueNotFoundError(f"Cue {cue_id} not found")
        if production_id is not None and row.production_id != production_id:
            raise CueNotFoundError(f"Cue {cue_id} not found")
        return row

    def create_cue(self, payload: CueCreate) -> Cue:
        if self.db.get(Production, payload.production_id) is None:
            raise CueValidationError(f"production {payload.production_id} not found")
        self._assert_asset(payload.asset_id, payload.production_id)

        row = Cue(
            production_id=payload.production_id,
            name=payload.name,
            cue_type=payload.cue_type,
            action=payload.action,
            asset_id=payload.asset_id,
            device_id=payload.device_id,
            parameters=dict(payload.parameters),
            enabled=payload.enabled,
            priority=payload.priority,
            cooldown_seconds=payload.cooldown_seconds,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_cue(self, cue_id: str, payload: CueUpdate) -> Cue:
        row = self.get_cue(cue_id)
        data = payload.model_dump(exclude_unset=True)

        clear_asset = bool(data.pop("clear_asset_id", False))
        clear_device = bool(data.pop("clear_device_id", False))
        clear_cooldown = bool(data.pop("clear_cooldown_seconds", False))

        if "name" in data and data["name"] is not None:
            row.name = data["name"]
        if "cue_type" in data and data["cue_type"] is not None:
            row.cue_type = data["cue_type"]
        if "action" in data and data["action"] is not None:
            row.action = data["action"]
        if "parameters" in data and data["parameters"] is not None:
            row.parameters = dict(data["parameters"])
        if "enabled" in data and data["enabled"] is not None:
            row.enabled = data["enabled"]
        if "priority" in data and data["priority"] is not None:
            row.priority = data["priority"]
        if clear_cooldown:
            row.cooldown_seconds = None
        elif "cooldown_seconds" in data:
            row.cooldown_seconds = data["cooldown_seconds"]

        if clear_asset:
            row.asset_id = None
        elif "asset_id" in data:
            row.asset_id = data["asset_id"]

        if clear_device:
            row.device_id = None
        elif "device_id" in data:
            row.device_id = data["device_id"]

        try:
            action = validate_cue_action(row.cue_type, row.action)
            params = validate_cue_parameters(row.cue_type, row.parameters)
            validate_cue_type_requirements(
                cue_type=row.cue_type,
                action=action,
                parameters=params,
                asset_id=row.asset_id,
            )
        except ValueError as exc:
            raise CueValidationError(str(exc)) from exc

        row.action = action
        row.parameters = params
        self._assert_asset(row.asset_id, row.production_id)

        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_cue(self, cue_id: str, *, production_id: str | None = None) -> None:
        row = self.get_cue(cue_id, production_id=production_id)
        self.db.delete(row)
        self.db.commit()

    def _assert_asset(self, asset_id: str | None, production_id: str) -> None:
        if asset_id is None:
            return
        asset = self.db.get(Asset, asset_id)
        if asset is None:
            raise CueValidationError(f"asset {asset_id} not found")
        if asset.production_id != production_id:
            raise CueValidationError("asset belongs to a different production")
