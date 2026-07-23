"""CRUD + upload service for Assets (storage via StorageBackend keys only)."""

from __future__ import annotations

import hashlib
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.asset import ASSET_TYPES, Asset
from app.models.production import Production
from app.models.tag import Tag
from app.schemas.asset import AssetCreate, AssetPreview, AssetUpdate
from app.storage.base import StorageBackend, StorageKeyError, StorageNotFoundError
from app.storage.filenames import UnsafeFilenameError, normalize_upload_filename
from app.storage.keys import build_asset_storage_key
from app.storage.mime import MimeDetectionError, detect_content

logger = logging.getLogger(__name__)

_PREVIEW_TEXT_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
    }
)
_PREVIEW_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
_PREVIEW_AUDIO_TYPES = frozenset(
    {"audio/wav", "audio/mpeg", "audio/aiff", "audio/mp3", "audio/x-wav", "audio/x-aiff"}
)
_PREVIEW_VIDEO_TYPES = frozenset({"video/mp4", "video/quicktime", "video/webm"})


class AssetError(Exception):
    """Base service error."""


class AssetNotFoundError(AssetError):
    pass


class AssetValidationError(AssetError):
    pass


class AssetService:
    def __init__(self, db: Session, storage: StorageBackend | None = None) -> None:
        self.db = db
        if storage is not None:
            self.storage = storage
        else:
            from app.storage import get_storage_backend

            self.storage = get_storage_backend()

    def list_assets(
        self,
        *,
        production_id: str | None = None,
        asset_type: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> list[Asset]:
        if asset_type is not None and asset_type not in ASSET_TYPES:
            raise AssetValidationError(f"invalid type: {asset_type}")

        stmt = (
            select(Asset)
            .options(selectinload(Asset.tags))
            .order_by(Asset.created_at.desc())
        )
        if production_id is not None:
            stmt = stmt.where(Asset.production_id == production_id)
        if asset_type is not None:
            stmt = stmt.where(Asset.type == asset_type)
        if tag_ids:
            # AND: asset must have every selected tag (same production scope enforced by FK).
            unique_tag_ids = list(dict.fromkeys(tag_ids))
            for tag_id in unique_tag_ids:
                stmt = stmt.where(Asset.tags.any(Tag.id == tag_id))
        return list(self.db.scalars(stmt).unique().all())

    def get_asset(self, asset_id: str, *, production_id: str | None = None) -> Asset:
        stmt = select(Asset).where(Asset.id == asset_id).options(selectinload(Asset.tags))
        if production_id is not None:
            stmt = stmt.where(Asset.production_id == production_id)
        row = self.db.scalar(stmt)
        if row is None:
            raise AssetNotFoundError(f"Asset {asset_id} not found")
        return row

    def create_asset(self, payload: AssetCreate) -> Asset:
        """Register metadata only — does not write or move files."""
        if self.db.get(Production, payload.production_id) is None:
            raise AssetValidationError(f"production {payload.production_id} not found")

        row = Asset(
            production_id=payload.production_id,
            name=payload.name,
            type=payload.type,
            original_filename=payload.original_filename,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            checksum=payload.checksum,
            description=payload.description,
            metadata_json=dict(payload.metadata),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def upload_asset(
        self,
        *,
        production_id: str,
        filename: str | None,
        stream: BinaryIO,
        content_type: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Asset:
        """Validate, store, and register an uploaded file for a production."""
        if self.db.get(Production, production_id) is None:
            raise AssetValidationError(f"production {production_id} not found")

        try:
            original_filename = normalize_upload_filename(filename)
        except UnsafeFilenameError as exc:
            raise AssetValidationError(str(exc)) from exc

        max_bytes = settings.asset_max_upload_bytes
        digest = hashlib.sha256()
        sample = b""
        size = 0

        tmp_path: Path | None = None
        storage_key: str | None = None
        committed = False
        try:
            with tempfile.NamedTemporaryFile(prefix="asset-upload-", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise AssetValidationError(
                            f"file exceeds maximum size of {max_bytes} bytes"
                        )
                    digest.update(chunk)
                    if len(sample) < 64 * 1024:
                        need = 64 * 1024 - len(sample)
                        sample += chunk[:need]
                    tmp.write(chunk)
                tmp.flush()

            if size == 0:
                raise AssetValidationError("empty file is not allowed")

            try:
                detected = detect_content(
                    sample=sample,
                    filename=original_filename,
                    claimed_content_type=content_type,
                    allowed_mime_types=settings.allowed_mime_type_set(),
                )
            except MimeDetectionError as exc:
                raise AssetValidationError(str(exc)) from exc

            asset_id = str(uuid4())
            storage_key = build_asset_storage_key(
                production_id=production_id,
                asset_id=asset_id,
                extension=detected.extension,
            )

            with tmp_path.open("rb") as stored:
                written = self.storage.put_stream(
                    storage_key,
                    stored,
                    content_type=detected.mime_type,
                )
            if written != size:
                raise AssetValidationError("stored size mismatch")

            display_name = (name or "").strip() or Path(original_filename).stem or "Asset"
            if len(display_name) > 200:
                display_name = display_name[:200]

            row = Asset(
                id=asset_id,
                production_id=production_id,
                name=display_name,
                type=detected.asset_type.value,
                original_filename=original_filename,
                storage_key=storage_key,
                mime_type=detected.mime_type,
                size_bytes=size,
                checksum=f"sha256:{digest.hexdigest()}",
                description=(description.strip() if description else None) or None,
                metadata_json={},
            )
            self.db.add(row)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            committed = True
            self.db.refresh(row)
            return row
        except Exception:
            if storage_key and not committed:
                try:
                    self.storage.delete(storage_key)
                except (StorageNotFoundError, StorageKeyError):
                    pass
            raise
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    def update_asset(self, asset_id: str, payload: AssetUpdate) -> Asset:
        row = self.get_asset(asset_id)
        data = payload.model_dump(exclude_unset=True)

        if "name" in data and data["name"] is not None:
            row.name = data["name"]
        if "type" in data and data["type"] is not None:
            row.type = data["type"]
        if "description" in data:
            row.description = data["description"]
        if "metadata" in data and data["metadata"] is not None:
            row.metadata_json = dict(data["metadata"])

        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.get_asset(row.id)

    def delete_asset(self, asset_id: str, *, production_id: str | None = None) -> None:
        """Delete metadata and the storage object referenced by ``storage_key``."""
        row = self.get_asset(asset_id, production_id=production_id)
        storage_key = row.storage_key
        self.db.delete(row)
        self.db.commit()
        try:
            self.storage.delete(storage_key)
        except StorageNotFoundError:
            logger.warning("asset %s storage object already missing: %s", asset_id, storage_key)
        except StorageKeyError:
            # Legacy/metadata-only rows may hold non-storage keys; never unlink arbitrary paths.
            logger.info(
                "asset %s skipped storage delete for unsafe or legacy key",
                asset_id,
            )

    def open_content(
        self,
        asset_id: str,
        *,
        production_id: str | None = None,
    ):
        """Return (asset, binary context manager) for streaming download."""
        row = self.get_asset(asset_id, production_id=production_id)
        try:
            handle = self.storage.open_read(row.storage_key)
        except StorageNotFoundError as exc:
            raise AssetNotFoundError(f"Asset file {asset_id} not found in storage") from exc
        except StorageKeyError as exc:
            raise AssetValidationError("invalid storage key") from exc
        return row, handle

    def preview_asset(
        self,
        asset_id: str,
        *,
        production_id: str | None = None,
    ) -> AssetPreview:
        row = self.get_asset(asset_id, production_id=production_id)
        mime = row.mime_type
        kind = "none"
        text_excerpt: str | None = None
        preview_available = False

        if mime in _PREVIEW_IMAGE_TYPES:
            kind = "image"
            preview_available = True
        elif mime in _PREVIEW_AUDIO_TYPES:
            kind = "audio"
            preview_available = True
        elif mime in _PREVIEW_VIDEO_TYPES:
            kind = "video"
            preview_available = True
        elif mime in _PREVIEW_TEXT_TYPES:
            kind = "text" if mime != "application/json" else "json"
            preview_available = True
            limit = settings.asset_preview_text_chars
            try:
                with self.storage.open_read(row.storage_key) as handle:
                    raw = handle.read(limit + 1)
                text = raw.decode("utf-8", errors="replace")
                if len(text) > limit:
                    text_excerpt = text[:limit] + "…"
                else:
                    text_excerpt = text
            except (StorageNotFoundError, StorageKeyError, UnicodeError):
                preview_available = False
                text_excerpt = None

        return AssetPreview(
            asset_id=row.id,
            production_id=row.production_id,
            mime_type=mime,
            kind=kind,  # type: ignore[arg-type]
            preview_available=preview_available,
            text_excerpt=text_excerpt,
            size_bytes=row.size_bytes,
            original_filename=row.original_filename,
        )
