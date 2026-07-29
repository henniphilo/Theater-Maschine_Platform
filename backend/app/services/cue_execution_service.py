"""Sole execution entry point for domain Cues.

Routes and UI must not call hardware bridges directly. Real sends go only
through Device OutputAdapters; dry-run plans without I/O.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.adapters import UnknownAdapterTypeError, build_adapter_for_device
from app.adapters.base import AdapterCommand, AdapterResult
from app.director.cues.safety import get_safety_state
from app.models.cue import Cue, CueType
from app.models.device import Device
from app.schemas.cue import CueExecutionResult
from app.services.cue_compat import domain_cue_to_planned_payload
from app.services.cue_service import CueNotFoundError, CueService
from app.services.device_service import DeviceNotFoundError, DeviceService

logger = logging.getLogger(__name__)

# Cue types that may execute without a Device (local / no hardware).
_DEVICE_OPTIONAL_TYPES = frozenset({CueType.WAIT.value, CueType.TEXT.value})


class CueExecutionError(Exception):
    """Base execution error."""


class CueExecutionRejectedError(CueExecutionError):
    pass


def planned_to_adapter_command(cue: Cue, planned: dict[str, Any]) -> AdapterCommand:
    """Map domain cue + planned payload to an AdapterCommand."""
    params: dict[str, Any] = dict(cue.parameters or {})
    params["cue_id"] = cue.id
    params["production_id"] = cue.production_id
    params["name"] = cue.name
    params["cue_type"] = cue.cue_type
    if cue.asset_id:
        params["asset_id"] = cue.asset_id
    if cue.device_id:
        params["device_id"] = cue.device_id

    director = planned.get("director") or {}
    if isinstance(director, dict):
        for key in ("visual", "sound", "light", "osc", "midi", "text", "wait"):
            nested = director.get(key)
            if isinstance(nested, dict):
                for nk, nv in nested.items():
                    params.setdefault(nk, nv)

    return AdapterCommand(action=cue.action, params=params)


class CueExecutionService:
    """Plan and dispatch Cue executions via Device adapters."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._cues = CueService(db)
        self._devices = DeviceService(db)

    def execute(
        self,
        cue_id: str,
        *,
        dry_run: bool = True,
        production_id: str | None = None,
    ) -> CueExecutionResult:
        cue = self._cues.get_cue(cue_id, production_id=production_id)
        return self.execute_cue(cue, dry_run=dry_run)

    def execute_cue(self, cue: Cue, *, dry_run: bool = True) -> CueExecutionResult:
        if not cue.enabled:
            return CueExecutionResult(
                cue_id=cue.id,
                production_id=cue.production_id,
                dry_run=dry_run,
                status="skipped",
                message="cue is disabled",
                planned={},
            )

        safety = get_safety_state()
        if not dry_run and safety.emergency_stop_active:
            raise CueExecutionRejectedError("emergency stop active; cue execution blocked")

        planned = domain_cue_to_planned_payload(cue)

        if dry_run:
            self._trace(cue, planned, event="cue_dry_run", status="planned")
            return CueExecutionResult(
                cue_id=cue.id,
                production_id=cue.production_id,
                dry_run=True,
                status="planned",
                message="dry-run: planned adapter payload (no hardware send)",
                planned=planned,
            )

        return self._execute_real(cue, planned)

    def _execute_real(self, cue: Cue, planned: dict[str, Any]) -> CueExecutionResult:
        if not cue.device_id:
            if cue.cue_type in _DEVICE_OPTIONAL_TYPES:
                self._trace(cue, planned, event="cue_execute", status="executed")
                return CueExecutionResult(
                    cue_id=cue.id,
                    production_id=cue.production_id,
                    dry_run=False,
                    status="executed",
                    message=f"executed locally (no device; cue_type={cue.cue_type})",
                    planned=planned,
                )
            raise CueExecutionRejectedError(
                "device_id required for real execution of this cue type"
            )

        try:
            device = self._devices.get_device(
                cue.device_id, production_id=cue.production_id
            )
        except DeviceNotFoundError as exc:
            raise CueExecutionRejectedError(str(exc)) from exc

        if device.production_id is not None and device.production_id != cue.production_id:
            raise CueExecutionRejectedError("device belongs to a different production")

        if not device.enabled:
            self._trace(cue, planned, event="cue_execute", status="skipped", device=device)
            return CueExecutionResult(
                cue_id=cue.id,
                production_id=cue.production_id,
                dry_run=False,
                status="skipped",
                message="device is disabled; no send",
                planned=planned,
            )

        command = planned_to_adapter_command(cue, planned)
        try:
            adapter = build_adapter_for_device(device)
        except UnknownAdapterTypeError as exc:
            raise CueExecutionRejectedError(str(exc)) from exc

        result = adapter.execute(command)
        return self._result_from_adapter(cue, planned, device, result)

    def _result_from_adapter(
        self,
        cue: Cue,
        planned: dict[str, Any],
        device: Device,
        result: AdapterResult,
    ) -> CueExecutionResult:
        status = "executed" if result.ok else "failed"
        message = result.message
        if result.dry_run and result.ok:
            message = f"{message} (adapter dry-run; no network send)"
        self._trace(
            cue,
            planned,
            event="cue_execute",
            status=status,
            device=device,
            adapter_dry_run=result.dry_run,
            adapter_ok=result.ok,
            adapter_message=result.message,
        )
        return CueExecutionResult(
            cue_id=cue.id,
            production_id=cue.production_id,
            dry_run=result.dry_run,
            status=status,  # type: ignore[arg-type]
            message=message,
            planned=planned,
        )

    def _trace(
        self,
        cue: Cue,
        planned: dict[str, Any],
        *,
        event: str,
        status: str,
        device: Device | None = None,
        **extra: Any,
    ) -> None:
        try:
            from app.director.outputs.signal_trace import emit_signal_trace_event

            detail: dict[str, Any] = {
                "production_id": cue.production_id,
                "action": cue.action,
                "name": cue.name,
                "planned": planned,
                **extra,
            }
            if device is not None:
                detail["device_id"] = device.id
                detail["adapter_type"] = device.adapter_type
            emit_signal_trace_event(
                event=event,
                status=status,
                cue_id=cue.id,
                bridge=cue.cue_type,
                detail=detail,
            )
        except Exception:
            logger.debug("signal trace unavailable for cue %s", cue.id, exc_info=True)


__all__ = [
    "CueExecutionError",
    "CueExecutionRejectedError",
    "CueExecutionService",
    "CueNotFoundError",
    "planned_to_adapter_command",
]
