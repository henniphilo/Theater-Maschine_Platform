"""CRUD service for the Production domain object."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.production import Production, ProductionStatus
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

    def get_active(self) -> tuple[str | None, Production | None]:
        production_id = active_production_store.get_active_production_id()
        if not production_id:
            return None, None
        row = self.db.get(Production, production_id)
        if row is None or row.status == ProductionStatus.ARCHIVED.value:
            active_production_store.clear_active_production_id()
            return None, None
        return production_id, row

    def set_active(self, production_id: str | None) -> tuple[str | None, Production | None]:
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
        return row.id, row

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
