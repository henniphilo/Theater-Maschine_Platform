from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.production import (
    ActiveProductionRead,
    ActiveProductionSet,
    ProductionCreate,
    ProductionRead,
    ProductionUpdate,
)
from app.services.production_service import (
    ProductionConflictError,
    ProductionNotFoundError,
    ProductionService,
    ProductionValidationError,
)

router = APIRouter(prefix="/productions", tags=["productions"])


def _service(db: Session = Depends(get_db)) -> ProductionService:
    return ProductionService(db)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProductionNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ProductionConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ProductionValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[ProductionRead])
def list_productions(
    include_archived: bool = Query(default=True),
    service: ProductionService = Depends(_service),
) -> list[ProductionRead]:
    rows = service.list_productions(include_archived=include_archived)
    return [ProductionRead.model_validate(row) for row in rows]


@router.post("", response_model=ProductionRead, status_code=status.HTTP_201_CREATED)
def create_production(
    payload: ProductionCreate,
    service: ProductionService = Depends(_service),
) -> ProductionRead:
    try:
        row = service.create_production(payload)
    except (ProductionConflictError, ProductionValidationError) as exc:
        raise _http_error(exc) from exc
    return ProductionRead.model_validate(row)


@router.get("/active", response_model=ActiveProductionRead)
def get_active_production(service: ProductionService = Depends(_service)) -> ActiveProductionRead:
    production_id, row = service.get_active()
    return ActiveProductionRead(
        production_id=production_id,
        production=ProductionRead.model_validate(row) if row else None,
    )


@router.put("/active", response_model=ActiveProductionRead)
def set_active_production(
    payload: ActiveProductionSet,
    service: ProductionService = Depends(_service),
) -> ActiveProductionRead:
    try:
        production_id, row = service.set_active(payload.production_id)
    except (ProductionNotFoundError, ProductionValidationError) as exc:
        raise _http_error(exc) from exc
    return ActiveProductionRead(
        production_id=production_id,
        production=ProductionRead.model_validate(row) if row else None,
    )


@router.get("/{production_id}", response_model=ProductionRead)
def get_production(
    production_id: str,
    service: ProductionService = Depends(_service),
) -> ProductionRead:
    try:
        row = service.get_production(production_id)
    except ProductionNotFoundError as exc:
        raise _http_error(exc) from exc
    return ProductionRead.model_validate(row)


@router.patch("/{production_id}", response_model=ProductionRead)
def update_production(
    production_id: str,
    payload: ProductionUpdate,
    service: ProductionService = Depends(_service),
) -> ProductionRead:
    try:
        row = service.update_production(production_id, payload)
    except (ProductionNotFoundError, ProductionConflictError, ProductionValidationError) as exc:
        raise _http_error(exc) from exc
    return ProductionRead.model_validate(row)


@router.post("/{production_id}/archive", response_model=ProductionRead)
def archive_production(
    production_id: str,
    service: ProductionService = Depends(_service),
) -> ProductionRead:
    try:
        row = service.archive_production(production_id)
    except ProductionNotFoundError as exc:
        raise _http_error(exc) from exc
    return ProductionRead.model_validate(row)
