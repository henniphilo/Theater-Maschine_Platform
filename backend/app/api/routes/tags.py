from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tag import TagCreate, TagRead
from app.services.tag_service import (
    TagConflictError,
    TagNotFoundError,
    TagService,
    TagValidationError,
)

router = APIRouter(prefix="/tags", tags=["tags"])


def _service(db: Session = Depends(get_db)) -> TagService:
    return TagService(db)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TagNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, TagConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, TagValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[TagRead])
def list_tags(
    production_id: str = Query(...),
    service: TagService = Depends(_service),
) -> list[TagRead]:
    try:
        rows = service.list_tags(production_id=production_id.strip())
    except TagValidationError as exc:
        raise _http_error(exc) from exc
    return [TagRead.model_validate(row) for row in rows]


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    service: TagService = Depends(_service),
) -> TagRead:
    try:
        row = service.create_tag(payload)
    except (TagConflictError, TagValidationError) as exc:
        raise _http_error(exc) from exc
    return TagRead.model_validate(row)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: str,
    production_id: str | None = Query(default=None),
    service: TagService = Depends(_service),
) -> Response:
    try:
        service.delete_tag(tag_id, production_id=production_id)
    except TagNotFoundError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
