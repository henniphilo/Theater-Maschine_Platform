import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.director.dialogue.models import DialogueEvent
from app.director.pipeline import get_director_pipeline
from app.director.recording import RecordingManager
from app.schemas.director import (
    DialogueEventRequest,
    DirectorProcessResponse,
    DirectorStatusResponse,
    RecordingRequest,
    RecordingStatusResponse,
    SafetyUpdateRequest,
)

router = APIRouter(prefix="/director", tags=["director"])

_pipeline = get_director_pipeline()
_recording = RecordingManager(touchdesigner=_pipeline.touchdesigner, media_db=_pipeline.media_db)


def _ensure_enabled() -> None:
    if not settings.director_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Director module is disabled",
        )


@router.post("/dialogue-event", response_model=DirectorProcessResponse)
def post_dialogue_event(payload: DialogueEventRequest) -> DirectorProcessResponse:
    _ensure_enabled()
    result = _pipeline.process(payload.to_event())
    return DirectorProcessResponse(
        event=result.event,
        decision=result.decision,
        executed=result.executed,
        blocked_reason=result.blocked_reason,
    )


@router.get("/status", response_model=DirectorStatusResponse)
def get_status() -> DirectorStatusResponse:
    _ensure_enabled()
    state = _pipeline.state
    last = state.last_result
    return DirectorStatusResponse(
        safety=_pipeline.safety.to_dict(),
        active_cues=list(_pipeline.scheduler.active_cues),
        last_event=state.last_event,
        last_decision=state.last_decision,
        last_executed=last.executed if last else None,
        last_blocked_reason=last.blocked_reason if last else None,
    )


@router.patch("/safety", response_model=DirectorStatusResponse)
def patch_safety(payload: SafetyUpdateRequest) -> DirectorStatusResponse:
    _ensure_enabled()
    updates = payload.model_dump(exclude_none=True)
    if updates:
        _pipeline.safety.update(**updates)
    return get_status()


@router.post("/emergency-stop", response_model=DirectorStatusResponse)
def emergency_stop() -> DirectorStatusResponse:
    _ensure_enabled()
    _pipeline.emergency_stop()
    return get_status()


@router.post("/emergency-clear", response_model=DirectorStatusResponse)
def emergency_clear() -> DirectorStatusResponse:
    _ensure_enabled()
    _pipeline.safety.clear_emergency_stop()
    return get_status()


@router.post("/record/start", response_model=RecordingStatusResponse)
def record_start(payload: RecordingRequest) -> RecordingStatusResponse:
    _ensure_enabled()
    session = _recording.start(payload.recording_id)
    return RecordingStatusResponse(active=True, recording_id=session.recording_id)


@router.post("/record/stop", response_model=RecordingStatusResponse)
def record_stop() -> RecordingStatusResponse:
    _ensure_enabled()
    session = _recording.stop()
    if session is None:
        return RecordingStatusResponse(active=False, recording_id=None)
    return RecordingStatusResponse(active=False, recording_id=session.recording_id)


@router.get("/record/status", response_model=RecordingStatusResponse)
def record_status() -> RecordingStatusResponse:
    _ensure_enabled()
    session = _recording.active_session
    if session is None:
        return RecordingStatusResponse(active=False)
    return RecordingStatusResponse(active=True, recording_id=session.recording_id)


async def _event_stream() -> AsyncIterator[str]:
    last_count = 0
    while True:
        history_len = len(_pipeline.state.history)
        if history_len > last_count:
            result = _pipeline.state.history[-1]
            payload = {
                "type": "director_update",
                "event": result.event.model_dump(mode="json"),
                "decision": result.decision.model_dump(mode="json"),
                "executed": result.executed,
                "blocked_reason": result.blocked_reason,
                "safety": _pipeline.safety.to_dict(),
                "active_cues": list(_pipeline.scheduler.active_cues),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            last_count = history_len
        await asyncio.sleep(0.5)


@router.get("/events")
async def director_events() -> StreamingResponse:
    _ensure_enabled()
    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def process_debate_turn_if_enabled(
    *,
    speaker: str,
    text: str,
    topic: str,
    created_at=None,
) -> DirectorProcessResponse | None:
    if not settings.director_enabled:
        return None
    from app.director.dialogue.builder import build_dialogue_event

    event = build_dialogue_event(
        speaker=speaker,
        text=text,
        topic=topic,
        created_at=created_at,
    )
    result = _pipeline.process(event)
    return DirectorProcessResponse(
        event=result.event,
        decision=result.decision,
        executed=result.executed,
        blocked_reason=result.blocked_reason,
    )
