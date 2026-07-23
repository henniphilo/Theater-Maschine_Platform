"""Sole execution entry point for domain Cues.

Routes and UI must not call hardware bridges directly. This milestone only
supports dry-run planning via the compatibility layer.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.cue import Cue
from app.schemas.cue import CueExecutionResult
from app.services.cue_compat import domain_cue_to_planned_payload
from app.services.cue_service import CueNotFoundError, CueService

logger = logging.getLogger(__name__)


class CueExecutionError(Exception):
    """Base execution error."""


class CueExecutionRejectedError(CueExecutionError):
    pass


class CueExecutionService:
    """Plan and (later) dispatch Cue executions.

    Hardware adapters are intentionally not invoked here yet. Real sends will
    go through Device adapters in a later milestone; until then only dry-run
    planning is allowed.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._cues = CueService(db)

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
        if not dry_run:
            # Fail closed: no hardware path from domain Cue execute yet.
            raise CueExecutionRejectedError(
                "real cue execution is disabled in this milestone; use dry_run=true"
            )

        if not cue.enabled:
            return CueExecutionResult(
                cue_id=cue.id,
                production_id=cue.production_id,
                dry_run=True,
                status="skipped",
                message="cue is disabled",
                planned={},
            )

        planned = domain_cue_to_planned_payload(cue)
        self._trace_dry_run(cue, planned)

        return CueExecutionResult(
            cue_id=cue.id,
            production_id=cue.production_id,
            dry_run=True,
            status="planned",
            message="dry-run: planned adapter payload (no hardware send)",
            planned=planned,
        )

    def _trace_dry_run(self, cue: Cue, planned: dict[str, Any]) -> None:
        try:
            from app.director.outputs.signal_trace import emit_signal_trace_event

            emit_signal_trace_event(
                event="cue_dry_run",
                status="planned",
                cue_id=cue.id,
                bridge=cue.cue_type,
                detail={
                    "production_id": cue.production_id,
                    "action": cue.action,
                    "name": cue.name,
                    "planned": planned,
                },
            )
        except Exception:
            # Trace is best-effort; never fail dry-run because of logging.
            logger.debug("signal trace unavailable for cue dry-run %s", cue.id, exc_info=True)


# Re-export for callers that catch missing cues via execution service.
__all__ = [
    "CueExecutionError",
    "CueExecutionRejectedError",
    "CueExecutionService",
    "CueNotFoundError",
]
