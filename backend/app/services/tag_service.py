"""CRUD + asset attach/detach for production-scoped Tags."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset
from app.models.production import Production
from app.models.tag import Tag
from app.schemas.tag import TagCreate
from app.services.asset_service import AssetNotFoundError, AssetService


class TagError(Exception):
    """Base service error."""


class TagNotFoundError(TagError):
    pass


class TagConflictError(TagError):
    pass


class TagValidationError(TagError):
    pass


class TagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._assets = AssetService(db)

    def list_tags(self, *, production_id: str) -> list[Tag]:
        if self.db.get(Production, production_id) is None:
            raise TagValidationError(f"production {production_id} not found")
        stmt = (
            select(Tag)
            .where(Tag.production_id == production_id)
            .order_by(Tag.name.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_tag(self, tag_id: str, *, production_id: str | None = None) -> Tag:
        row = self.db.get(Tag, tag_id)
        if row is None:
            raise TagNotFoundError(f"Tag {tag_id} not found")
        if production_id is not None and row.production_id != production_id:
            raise TagNotFoundError(f"Tag {tag_id} not found")
        return row

    def create_tag(self, payload: TagCreate) -> Tag:
        if self.db.get(Production, payload.production_id) is None:
            raise TagValidationError(f"production {payload.production_id} not found")

        existing = self._find_by_name(payload.production_id, payload.name)
        if existing is not None:
            raise TagConflictError(
                f"tag '{payload.name}' already exists in production {payload.production_id}"
            )

        row = Tag(production_id=payload.production_id, name=payload.name)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise TagConflictError(
                f"tag '{payload.name}' already exists in production {payload.production_id}"
            ) from exc
        self.db.refresh(row)
        return row

    def get_or_create_tag(self, *, production_id: str, name: str) -> Tag:
        cleaned = name.strip()
        if not cleaned:
            raise TagValidationError("name must not be empty")
        if len(cleaned) > 100:
            raise TagValidationError("name must be at most 100 characters")

        if self.db.get(Production, production_id) is None:
            raise TagValidationError(f"production {production_id} not found")

        existing = self._find_by_name(production_id, cleaned)
        if existing is not None:
            return existing

        row = Tag(production_id=production_id, name=cleaned)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._find_by_name(production_id, cleaned)
            if existing is not None:
                return existing
            raise
        self.db.refresh(row)
        return row

    def delete_tag(self, tag_id: str, *, production_id: str | None = None) -> None:
        row = self.get_tag(tag_id, production_id=production_id)
        self.db.delete(row)
        self.db.commit()

    def attach_tag_to_asset(
        self,
        asset_id: str,
        *,
        tag_id: str | None = None,
        name: str | None = None,
        production_id: str | None = None,
    ) -> Asset:
        asset = self._load_asset_with_tags(asset_id, production_id=production_id)

        if tag_id is not None:
            tag = self.get_tag(tag_id)
            if tag.production_id != asset.production_id:
                raise TagValidationError("tag belongs to a different production")
        elif name is not None:
            tag = self.get_or_create_tag(production_id=asset.production_id, name=name)
        else:
            raise TagValidationError("exactly one of tag_id or name is required")

        if tag.id not in {t.id for t in asset.tags}:
            asset.tags.append(tag)
            asset.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(asset)
        return self._load_asset_with_tags(asset.id)

    def detach_tag_from_asset(
        self,
        asset_id: str,
        tag_id: str,
        *,
        production_id: str | None = None,
    ) -> Asset:
        asset = self._load_asset_with_tags(asset_id, production_id=production_id)
        tag = self.get_tag(tag_id)
        if tag.production_id != asset.production_id:
            # Fail closed — do not reveal cross-production tag existence via detach.
            raise TagNotFoundError(f"Tag {tag_id} not found")

        before = len(asset.tags)
        asset.tags = [t for t in asset.tags if t.id != tag_id]
        if len(asset.tags) == before:
            raise TagNotFoundError(f"Tag {tag_id} is not attached to asset {asset_id}")

        asset.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self._load_asset_with_tags(asset.id)

    def _find_by_name(self, production_id: str, name: str) -> Tag | None:
        stmt = select(Tag).where(
            Tag.production_id == production_id,
            func.lower(Tag.name) == name.lower(),
        )
        return self.db.scalar(stmt)

    def _load_asset_with_tags(
        self,
        asset_id: str,
        *,
        production_id: str | None = None,
    ) -> Asset:
        # Raises AssetNotFoundError if missing / wrong production.
        self._assets.get_asset(asset_id, production_id=production_id)

        stmt = (
            select(Asset)
            .where(Asset.id == asset_id)
            .options(selectinload(Asset.tags))
        )
        if production_id is not None:
            stmt = stmt.where(Asset.production_id == production_id)
        row = self.db.scalar(stmt)
        if row is None:
            raise AssetNotFoundError(f"Asset {asset_id} not found")
        return row
