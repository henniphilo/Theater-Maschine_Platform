"""Admin API for one-shot Burgtheater production import."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.burgtheater_import import BurgtheaterImportRequest, BurgtheaterImportResponse
from app.services.burgtheater_import import BurgtheaterImportOptions, run_burgtheater_import
from app.storage import get_storage_backend
from app.storage.base import StorageBackend

router = APIRouter(prefix="/admin/imports", tags=["admin-import"])


@router.post(
    "/burgtheater",
    response_model=BurgtheaterImportResponse,
    summary="Import Burgtheater reference production (dry-run by default)",
)
def import_burgtheater(
    payload: BurgtheaterImportRequest,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> BurgtheaterImportResponse:
    """Analyze or apply Burgtheater import. Source files are never modified.

    Call with ``dry_run=true`` (default) first to obtain the import report and
    warnings. Set ``dry_run=false`` to persist. Devices are always created as
    disabled dry-run templates; hardware addresses are not imported unless
    explicitly requested (and even then sensitive keys are refused).
    """
    try:
        options = BurgtheaterImportOptions(
            dry_run=payload.dry_run,
            include_hardware_addresses=payload.include_hardware_addresses,
            hardware_address_overlay=dict(payload.hardware_address_overlay or {}),
            copy_media_into_storage=payload.copy_media_into_storage,
            repo_root=Path(payload.repo_root) if payload.repo_root else None,
            data_dir=Path(payload.data_dir) if payload.data_dir else None,
            media_dir=Path(payload.media_dir) if payload.media_dir else None,
        )
        report = run_burgtheater_import(db, storage=storage, options=options)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface import failures as 500 with message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Burgtheater import failed: {exc}",
        ) from exc

    return BurgtheaterImportResponse.model_validate(report.to_dict())
