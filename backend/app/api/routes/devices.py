from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.device import (
    DeviceConnectionTestResult,
    DeviceCreate,
    DeviceHealthResult,
    DeviceRead,
    DeviceUpdate,
)
from app.services.device_service import (
    DeviceNotFoundError,
    DeviceService,
    DeviceValidationError,
)

router = APIRouter(prefix="/devices", tags=["devices"])


def _service(db: Session = Depends(get_db)) -> DeviceService:
    return DeviceService(db)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DeviceNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DeviceValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[DeviceRead])
def list_devices(
    production_id: str | None = Query(default=None),
    adapter_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    include_global: bool = Query(default=True),
    service: DeviceService = Depends(_service),
) -> list[DeviceRead]:
    try:
        rows = service.list_devices(
            production_id=production_id,
            adapter_type=adapter_type,
            enabled=enabled,
            include_global=include_global,
        )
    except DeviceValidationError as exc:
        raise _http_error(exc) from exc
    return [service.to_read(row) for row in rows]


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    service: DeviceService = Depends(_service),
) -> DeviceRead:
    try:
        row = service.create_device(payload)
    except (DeviceValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return service.to_read(row)


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(
    device_id: str,
    production_id: str | None = Query(default=None),
    service: DeviceService = Depends(_service),
) -> DeviceRead:
    try:
        row = service.get_device(device_id, production_id=production_id)
    except DeviceNotFoundError as exc:
        raise _http_error(exc) from exc
    return service.to_read(row)


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    service: DeviceService = Depends(_service),
) -> DeviceRead:
    try:
        row = service.update_device(device_id, payload)
    except (DeviceNotFoundError, DeviceValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return service.to_read(row)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: str,
    production_id: str | None = Query(default=None),
    service: DeviceService = Depends(_service),
) -> Response:
    try:
        service.delete_device(device_id, production_id=production_id)
    except DeviceNotFoundError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{device_id}/test-connection", response_model=DeviceConnectionTestResult)
def test_device_connection(
    device_id: str,
    production_id: str | None = Query(default=None),
    service: DeviceService = Depends(_service),
) -> DeviceConnectionTestResult:
    try:
        return service.test_connection(device_id, production_id=production_id)
    except (DeviceNotFoundError, DeviceValidationError) as exc:
        raise _http_error(exc) from exc


@router.get("/{device_id}/health", response_model=DeviceHealthResult)
def device_health(
    device_id: str,
    production_id: str | None = Query(default=None),
    service: DeviceService = Depends(_service),
) -> DeviceHealthResult:
    try:
        return service.health(device_id, production_id=production_id)
    except (DeviceNotFoundError, DeviceValidationError) as exc:
        raise _http_error(exc) from exc
