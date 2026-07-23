from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cue import (
    CueCreate,
    CueExecuteRequest,
    CueExecutionResult,
    CueRead,
    CueUpdate,
    LegacyCueSummary,
)
from app.services.cue_compat import list_legacy_catalog_summaries
from app.services.cue_execution_service import (
    CueExecutionRejectedError,
    CueExecutionService,
)
from app.services.cue_service import (
    CueNotFoundError,
    CueService,
    CueValidationError,
)

router = APIRouter(prefix="/cues", tags=["cues"])


def _service(db: Session = Depends(get_db)) -> CueService:
    return CueService(db)


def _execution_service(db: Session = Depends(get_db)) -> CueExecutionService:
    return CueExecutionService(db)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CueNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CueExecutionRejectedError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, CueValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("/legacy", response_model=list[LegacyCueSummary])
def list_legacy_cues(
    source: str | None = Query(default=None),
) -> list[LegacyCueSummary]:
    """Read-only view of existing JSON/CSV catalog cues (compatibility)."""
    rows = list_legacy_catalog_summaries()
    if source is not None:
        rows = [row for row in rows if row.source == source]
    return rows


@router.get("", response_model=list[CueRead])
def list_cues(
    production_id: str | None = Query(default=None),
    cue_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    service: CueService = Depends(_service),
) -> list[CueRead]:
    try:
        rows = service.list_cues(
            production_id=production_id,
            cue_type=cue_type,
            enabled=enabled,
        )
    except CueValidationError as exc:
        raise _http_error(exc) from exc
    return [CueRead.model_validate(row) for row in rows]


@router.post("", response_model=CueRead, status_code=status.HTTP_201_CREATED)
def create_cue(
    payload: CueCreate,
    service: CueService = Depends(_service),
) -> CueRead:
    try:
        row = service.create_cue(payload)
    except (CueValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return CueRead.model_validate(row)


@router.get("/{cue_id}", response_model=CueRead)
def get_cue(
    cue_id: str,
    production_id: str | None = Query(default=None),
    service: CueService = Depends(_service),
) -> CueRead:
    try:
        row = service.get_cue(cue_id, production_id=production_id)
    except CueNotFoundError as exc:
        raise _http_error(exc) from exc
    return CueRead.model_validate(row)


@router.patch("/{cue_id}", response_model=CueRead)
def update_cue(
    cue_id: str,
    payload: CueUpdate,
    service: CueService = Depends(_service),
) -> CueRead:
    try:
        row = service.update_cue(cue_id, payload)
    except (CueNotFoundError, CueValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return CueRead.model_validate(row)


@router.delete("/{cue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cue(
    cue_id: str,
    production_id: str | None = Query(default=None),
    service: CueService = Depends(_service),
) -> Response:
    try:
        service.delete_cue(cue_id, production_id=production_id)
    except CueNotFoundError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{cue_id}/execute", response_model=CueExecutionResult)
def execute_cue(
    cue_id: str,
    payload: CueExecuteRequest | None = None,
    production_id: str | None = Query(default=None),
    service: CueExecutionService = Depends(_execution_service),
) -> CueExecutionResult:
    """Execute a cue via CueExecutionService only (dry-run in this milestone)."""
    body = payload or CueExecuteRequest()
    try:
        return service.execute(
            cue_id,
            dry_run=body.dry_run,
            production_id=production_id,
        )
    except (CueNotFoundError, CueExecutionRejectedError) as exc:
        raise _http_error(exc) from exc
