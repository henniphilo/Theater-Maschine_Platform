"""CRUD service for the Production domain object."""

from __future__ import annotations

import copy
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cue import Cue
from app.models.device import Device
from app.models.production import Production, ProductionStatus
from app.models.rule import Rule
from app.models.tag import Tag, asset_tags
from app.schemas.production import ProductionCreate, ProductionUpdate
from app.services import active_production as active_production_store

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")


class ProductionError(Exception):
    """Base service error."""


class ProductionNotFoundError(ProductionError):
    pass


class ProductionConflictError(ProductionError):
    pass


class ProductionValidationError(ProductionError):
    pass


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_SAFE.sub("-", ascii_text.lower()).strip("-")
    return slug[:200] or "production"


def _director_switch_blocked() -> tuple[bool, str | None]:
    """True when active production must not change without force."""
    try:
        from app.director.cues.safety import get_safety_state
        from app.director.pipeline import get_director_pipeline

        safety = get_safety_state()
        if safety.emergency_stop_active:
            return True, "emergency stop active"
        pipeline = get_director_pipeline()
        if pipeline.scheduler.active_cues:
            return True, "director has active cues"
    except Exception:
        return False, None
    return False, None


class ProductionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_productions(self, *, include_archived: bool = True) -> list[Production]:
        stmt = select(Production).order_by(Production.created_at.desc())
        if not include_archived:
            stmt = stmt.where(Production.status != ProductionStatus.ARCHIVED.value)
        return list(self.db.scalars(stmt).all())

    def get_production(self, production_id: str) -> Production:
        row = self.db.get(Production, production_id)
        if row is None:
            raise ProductionNotFoundError(f"Production {production_id} not found")
        return row

    def get_by_slug(self, slug: str) -> Production | None:
        return self.db.scalar(select(Production).where(Production.slug == slug))

    def create_production(self, payload: ProductionCreate) -> Production:
        base_slug = slugify(payload.slug or payload.name)
        slug = self._unique_slug(base_slug)
        row = Production(
            name=payload.name,
            slug=slug,
            description=payload.description,
            status=ProductionStatus.DRAFT.value,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ProductionConflictError("slug already exists") from exc
        self.db.refresh(row)
        return row

    def update_production(self, production_id: str, payload: ProductionUpdate) -> Production:
        row = self.get_production(production_id)
        data = payload.model_dump(exclude_unset=True)

        if "status" in data and data["status"] is not None:
            self._apply_status(row, data["status"])

        if "name" in data and data["name"] is not None:
            row.name = data["name"]
        if "description" in data:
            row.description = data["description"]
        if "slug" in data and data["slug"] is not None:
            new_slug = slugify(data["slug"])
            if new_slug != row.slug:
                if self.get_by_slug(new_slug) is not None:
                    raise ProductionConflictError("slug already exists")
                row.slug = new_slug

        row.updated_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ProductionConflictError("slug already exists") from exc
        self.db.refresh(row)
        return row

    def archive_production(self, production_id: str) -> Production:
        row = self.get_production(production_id)
        self._apply_status(row, ProductionStatus.ARCHIVED.value)
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)

        if active_production_store.get_active_production_id() == production_id:
            active_production_store.clear_active_production_id()
        return row

    def duplicate_production(
        self,
        production_id: str,
        *,
        name: str | None = None,
        slug: str | None = None,
    ) -> Production:
        """Deep-copy structure; share storage_key for assets (no binary copy)."""
        source = self.get_production(production_id)
        new_name = (name or f"{source.name} (Kopie)").strip()
        base_slug = slugify(slug or f"{source.slug}-copy")
        new_slug = self._unique_slug(base_slug)

        clone = Production(
            name=new_name,
            slug=new_slug,
            description=source.description,
            status=ProductionStatus.DRAFT.value,
        )
        self.db.add(clone)
        self.db.flush()

        tag_map = self._copy_tags(source.id, clone.id)
        asset_map = self._copy_assets(source.id, clone.id, tag_map)
        device_map = self._copy_devices(source.id, clone.id)
        cue_map = self._copy_cues(source.id, clone.id, asset_map, device_map)
        self._copy_rules(source.id, clone.id, cue_map)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ProductionConflictError("duplicate failed") from exc
        self.db.refresh(clone)
        return clone

    def get_active(self) -> tuple[str | None, Production | None]:
        production_id = active_production_store.get_active_production_id()
        if not production_id:
            return None, None
        row = self.db.get(Production, production_id)
        if row is None or row.status == ProductionStatus.ARCHIVED.value:
            active_production_store.clear_active_production_id()
            return None, None
        return production_id, row

    def set_active(
        self,
        production_id: str | None,
        *,
        force: bool = False,
    ) -> tuple[str | None, Production | None]:
        current = active_production_store.get_active_production_id()
        if production_id == current:
            return self.get_active()

        blocked, reason = _director_switch_blocked()
        if blocked and not force:
            raise ProductionValidationError(
                f"cannot change active production while {reason}; "
                "stop/clear director or pass force=true"
            )

        if force and blocked:
            try:
                from app.director.cues.safety import get_safety_state
                from app.director.pipeline import get_director_pipeline
                from app.services.director_production_context import (
                    emergency_stop_active_production_devices,
                )

                pipeline = get_director_pipeline()
                get_safety_state().emergency_stop()
                pipeline.scheduler.clear_active()
                pipeline.projectors.reset()
                emergency_stop_active_production_devices(self.db)
            except Exception:
                pass

        if production_id is None:
            active_production_store.clear_active_production_id()
            return None, None

        row = self.get_production(production_id)
        if row.status == ProductionStatus.ARCHIVED.value:
            raise ProductionValidationError("archived productions cannot be set active")

        if row.status == ProductionStatus.DRAFT.value:
            row.status = ProductionStatus.ACTIVE_ELIGIBLE.value
            row.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(row)

        active_production_store.set_active_production_id(row.id)
        try:
            from app.director.pipeline import get_director_pipeline

            get_director_pipeline().projectors.reconfigure_from_active_production()
        except Exception:
            pass
        return row.id, row

    def _copy_tags(self, source_id: str, dest_id: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        rows = list(self.db.scalars(select(Tag).where(Tag.production_id == source_id)).all())
        for row in rows:
            new_id = str(uuid4())
            mapping[row.id] = new_id
            self.db.add(Tag(id=new_id, production_id=dest_id, name=row.name))
        self.db.flush()
        return mapping

    def _copy_assets(
        self,
        source_id: str,
        dest_id: str,
        tag_map: dict[str, str],
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        rows = list(self.db.scalars(select(Asset).where(Asset.production_id == source_id)).all())
        for row in rows:
            new_id = str(uuid4())
            mapping[row.id] = new_id
            clone = Asset(
                id=new_id,
                production_id=dest_id,
                name=row.name,
                type=row.type,
                original_filename=row.original_filename,
                storage_key=row.storage_key,
                mime_type=row.mime_type,
                size_bytes=row.size_bytes,
                checksum=row.checksum,
                description=row.description,
                metadata_json=copy.deepcopy(row.metadata_json or {}),
            )
            self.db.add(clone)
            self.db.flush()
            for tag in row.tags:
                new_tag_id = tag_map.get(tag.id)
                if new_tag_id:
                    self.db.execute(
                        asset_tags.insert().values(asset_id=new_id, tag_id=new_tag_id)
                    )
        return mapping

    def _copy_devices(self, source_id: str, dest_id: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        rows = list(
            self.db.scalars(select(Device).where(Device.production_id == source_id)).all()
        )
        for row in rows:
            new_id = str(uuid4())
            mapping[row.id] = new_id
            self.db.add(
                Device(
                    id=new_id,
                    production_id=dest_id,
                    name=row.name,
                    adapter_type=row.adapter_type,
                    enabled=row.enabled,
                    configuration=copy.deepcopy(row.configuration or {}),
                    configuration_sealed=row.configuration_sealed,
                )
            )
        self.db.flush()
        return mapping

    def _copy_cues(
        self,
        source_id: str,
        dest_id: str,
        asset_map: dict[str, str],
        device_map: dict[str, str],
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        rows = list(self.db.scalars(select(Cue).where(Cue.production_id == source_id)).all())
        for row in rows:
            new_id = str(uuid4())
            mapping[row.id] = new_id
            self.db.add(
                Cue(
                    id=new_id,
                    production_id=dest_id,
                    name=row.name,
                    cue_type=row.cue_type,
                    asset_id=asset_map.get(row.asset_id) if row.asset_id else None,
                    device_id=device_map.get(row.device_id) if row.device_id else None,
                    action=row.action,
                    parameters=copy.deepcopy(row.parameters or {}),
                    enabled=row.enabled,
                    priority=row.priority,
                    cooldown_seconds=row.cooldown_seconds,
                )
            )
        self.db.flush()
        return mapping

    def _copy_rules(
        self,
        source_id: str,
        dest_id: str,
        cue_map: dict[str, str],
    ) -> None:
        rows = list(self.db.scalars(select(Rule).where(Rule.production_id == source_id)).all())
        for row in rows:
            actions = self._remap_rule_actions(copy.deepcopy(row.actions or []), cue_map)
            self.db.add(
                Rule(
                    id=str(uuid4()),
                    production_id=dest_id,
                    name=row.name,
                    enabled=row.enabled,
                    priority=row.priority,
                    conditions=copy.deepcopy(row.conditions or []),
                    actions=actions,
                    cooldown_seconds=row.cooldown_seconds,
                )
            )
        self.db.flush()

    @staticmethod
    def _remap_rule_actions(
        actions: list[dict[str, Any]],
        cue_map: dict[str, str],
    ) -> list[dict[str, Any]]:
        for action in actions:
            cue_id = action.get("cue_id")
            if isinstance(cue_id, str) and cue_id in cue_map:
                action["cue_id"] = cue_map[cue_id]
        return actions

    def _apply_status(self, row: Production, status: str) -> None:
        if status == ProductionStatus.ARCHIVED.value:
            row.status = ProductionStatus.ARCHIVED.value
            if row.archived_at is None:
                row.archived_at = datetime.now(timezone.utc)
            return
        if status in (
            ProductionStatus.DRAFT.value,
            ProductionStatus.ACTIVE_ELIGIBLE.value,
        ):
            row.status = status
            row.archived_at = None
            return
        raise ProductionValidationError(f"invalid status: {status}")

    def _unique_slug(self, base: str) -> str:
        candidate = base
        suffix = 2
        while self.get_by_slug(candidate) is not None:
            trimmed = base[: max(1, 200 - len(str(suffix)) - 1)]
            candidate = f"{trimmed}-{suffix}"
            suffix += 1
        return candidate
