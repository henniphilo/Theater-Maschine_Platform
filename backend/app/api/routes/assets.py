from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.asset import AssetPreview, AssetRead, AssetUpdate
from app.schemas.tag import AssetTagAttach
from app.services.asset_service import (
    AssetNotFoundError,
    AssetService,
    AssetValidationError,
)
from app.services.tag_service import (
    TagConflictError,
    TagNotFoundError,
    TagService,
    TagValidationError,
)
from app.storage import get_storage_backend
from app.storage.base import StorageBackend

router = APIRouter(prefix="/assets", tags=["assets"])


def _service(
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> AssetService:
    return AssetService(db, storage=storage)


def _tag_service(db: Session = Depends(get_db)) -> TagService:
    return TagService(db)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (AssetNotFoundError, TagNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, TagConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (AssetValidationError, TagValidationError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[AssetRead])
def list_assets(
    production_id: str | None = Query(default=None),
    asset_type: str | None = Query(default=None, alias="type"),
    tag_id: list[str] | None = Query(default=None),
    service: AssetService = Depends(_service),
) -> list[AssetRead]:
    try:
        rows = service.list_assets(
            production_id=production_id,
            asset_type=asset_type,
            tag_ids=tag_id,
        )
    except AssetValidationError as exc:
        raise _http_error(exc) from exc
    return [AssetRead.model_validate(row) for row in rows]


@router.post("/upload", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    production_id: str = Form(...),
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    service: AssetService = Depends(_service),
) -> AssetRead:
    try:
        row = service.upload_asset(
            production_id=production_id.strip(),
            filename=file.filename,
            stream=file.file,
            content_type=file.content_type,
            name=name,
            description=description,
        )
    except (AssetNotFoundError, AssetValidationError) as exc:
        raise _http_error(exc) from exc
    finally:
        await file.close()
    return AssetRead.model_validate(row)


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: str,
    production_id: str | None = Query(default=None),
    service: AssetService = Depends(_service),
) -> AssetRead:
    try:
        row = service.get_asset(asset_id, production_id=production_id)
    except AssetNotFoundError as exc:
        raise _http_error(exc) from exc
    return AssetRead.model_validate(row)


@router.get("/{asset_id}/preview", response_model=AssetPreview)
def preview_asset(
    asset_id: str,
    production_id: str = Query(...),
    service: AssetService = Depends(_service),
) -> AssetPreview:
    try:
        return service.preview_asset(asset_id, production_id=production_id)
    except (AssetNotFoundError, AssetValidationError) as exc:
        raise _http_error(exc) from exc


@router.get("/{asset_id}/content")
def download_asset(
    asset_id: str,
    production_id: str = Query(...),
    service: AssetService = Depends(_service),
) -> StreamingResponse:
    try:
        row, handle_cm = service.open_content(asset_id, production_id=production_id)
    except (AssetNotFoundError, AssetValidationError) as exc:
        raise _http_error(exc) from exc

    def iter_file():
        with handle_cm as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{row.original_filename}"',
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(
        iter_file(),
        media_type=row.mime_type,
        headers=headers,
    )


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    service: AssetService = Depends(_service),
) -> AssetRead:
    try:
        row = service.update_asset(asset_id, payload)
    except (AssetNotFoundError, AssetValidationError) as exc:
        raise _http_error(exc) from exc
    return AssetRead.model_validate(row)


@router.post("/{asset_id}/tags", response_model=AssetRead)
def attach_tag(
    asset_id: str,
    payload: AssetTagAttach,
    production_id: str | None = Query(default=None),
    service: TagService = Depends(_tag_service),
) -> AssetRead:
    try:
        row = service.attach_tag_to_asset(
            asset_id,
            tag_id=payload.tag_id,
            name=payload.name,
            production_id=production_id,
        )
    except (AssetNotFoundError, TagNotFoundError, TagValidationError, TagConflictError) as exc:
        raise _http_error(exc) from exc
    return AssetRead.model_validate(row)


@router.delete("/{asset_id}/tags/{tag_id}", response_model=AssetRead)
def detach_tag(
    asset_id: str,
    tag_id: str,
    production_id: str | None = Query(default=None),
    service: TagService = Depends(_tag_service),
) -> AssetRead:
    try:
        row = service.detach_tag_from_asset(
            asset_id,
            tag_id,
            production_id=production_id,
        )
    except (AssetNotFoundError, TagNotFoundError, TagValidationError) as exc:
        raise _http_error(exc) from exc
    return AssetRead.model_validate(row)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: str,
    production_id: str | None = Query(default=None),
    service: AssetService = Depends(_service),
) -> Response:
    try:
        service.delete_asset(asset_id, production_id=production_id)
    except AssetNotFoundError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
