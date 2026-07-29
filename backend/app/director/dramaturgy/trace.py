"""Emit dramaturgy decision events to signal trace and optional DB."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from app.director.cues.cue_models import (
    DecisionKind,
    DecisionStatus,
    DramaturgyDecision,
    DramaturgyDecisionEvent,
)
from app.director.dialogue.models import DialogueEvent
from app.director.dramaturgy.reason_short import enrich_decision_metadata
from app.director.outputs.signal_trace import RequestTrace, emit_signal_trace_event
from app.director.run_state import get_director_run_state


def _new_decision_id() -> str:
    return f"decision-{secrets.token_hex(4)}"


def _primary_cue_id(decision: DramaturgyDecision) -> str | None:
    if decision.visual and decision.visual.clip_id:
        return decision.visual.clip_id
    if decision.sound and decision.sound.cue_id:
        return decision.sound.cue_id
    if decision.light and decision.light.scene_id:
        return decision.light.scene_id
    return None


def build_decision_event(
    decision: DramaturgyDecision,
    *,
    event: DialogueEvent | None = None,
    session_id: str | None = None,
    status: DecisionStatus = DecisionStatus.SCHEDULED,
    intensity_before: float | None = None,
    intensity_after: float | None = None,
) -> DramaturgyDecisionEvent:
    enriched = enrich_decision_metadata(decision.model_copy(deep=True))
    text_snippet = (event.text if event else "")[:200]
    kind = enriched.decision_kind or DecisionKind.EXECUTE
    function = enriched.dramaturgical_function
    if function is None:
        from app.director.dramaturgy.reason_short import infer_dramaturgical_function

        function = infer_dramaturgical_function(
            mood=enriched.mood,
            intensity=enriched.intensity,
            tags=list(enriched.tags),
        )
    return DramaturgyDecisionEvent(
        decision_id=_new_decision_id(),
        session_id=session_id,
        text_event_id=str(event.timestamp) if event else None,
        cue_id=_primary_cue_id(enriched),
        decision=kind,
        reason_short=enriched.reason_short or enriched.reason[:160],
        dramaturgical_function=function,
        confidence=enriched.confidence,
        intensity_before=intensity_before,
        intensity_after=intensity_after or enriched.intensity,
        decision_status=status,
        text_snippet=text_snippet,
        created_at=datetime.now(UTC),
    )


def emit_dramaturgy_decision(
    decision: DramaturgyDecision,
    *,
    event: DialogueEvent | None = None,
    request_trace: RequestTrace | None = None,
    executed: bool = False,
    blocked_reason: str | None = None,
    status: DecisionStatus | None = None,
    intensity_before: float | None = None,
) -> DramaturgyDecisionEvent:
    run = get_director_run_state().current()
    resolved_status = status or (DecisionStatus.EXECUTED if executed else DecisionStatus.SCHEDULED)
    if blocked_reason:
        resolved_status = DecisionStatus.CANCELLED

    decision_event = build_decision_event(
        decision,
        event=event,
        session_id=run.run_id,
        status=resolved_status,
        intensity_before=intensity_before,
    )
    payload = decision_event.model_dump(mode="json")
    payload["run_epoch"] = run.run_epoch
    payload["executed"] = executed
    if blocked_reason:
        payload["blocked_reason"] = blocked_reason

    emit_signal_trace_event(
        "dramaturgy_decision",
        status=resolved_status.value,
        request_trace=request_trace,
        **payload,
    )
    _persist_decision_event(decision_event, payload, executed=executed, blocked_reason=blocked_reason)
    return decision_event


def _persist_decision_event(
    decision_event: DramaturgyDecisionEvent,
    payload: dict[str, object],
    *,
    executed: bool,
    blocked_reason: str | None,
) -> None:
    try:
        import json

        from app.db.session import SessionLocal
        from app.models.dramaturgy_decision_event import DramaturgyDecisionEventRow
    except ImportError:
        return

    session = SessionLocal()
    try:
        row = DramaturgyDecisionEventRow(
            id=decision_event.decision_id,
            session_id=decision_event.session_id,
            text_snippet=decision_event.text_snippet,
            cue_id=decision_event.cue_id,
            decision_kind=decision_event.decision.value,
            reason_short=decision_event.reason_short,
            dramaturgical_function=decision_event.dramaturgical_function.value,
            confidence=decision_event.confidence,
            decision_status=decision_event.decision_status.value,
            executed=executed,
            blocked_reason=blocked_reason,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
        session.add(row)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
