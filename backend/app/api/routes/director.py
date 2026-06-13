import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.director.pipeline import get_director_pipeline
from app.director.recording import RecordingManager
from app.director.cues.cue_models import OscCommand
from app.schemas.director import (
    DialogueEventRequest,
    DirectorProcessResponse,
    DirectorStatusResponse,
    ExecuteRequest,
    ExecuteResponse,
    OscTestRequest,
    OscTestResponse,
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


def _to_response(result) -> DirectorProcessResponse:
    return DirectorProcessResponse(
        event=result.event,
        decision=result.decision,
        executed=result.executed,
        blocked_reason=result.blocked_reason,
        planned_commands=result.planned_commands,
        osc_commands=result.osc_commands,
    )


def _status_response() -> DirectorStatusResponse:
    state = _pipeline.state
    last = state.last_result
    return DirectorStatusResponse(
        safety=_pipeline.safety.to_dict(),
        active_cues=list(_pipeline.scheduler.active_cues),
        last_event=state.last_event,
        last_decision=state.last_decision,
        last_executed=last.executed if last else None,
        last_blocked_reason=last.blocked_reason if last else None,
        last_planned_commands=last.planned_commands if last else [],
        last_osc_commands=state.last_osc_commands,
    )


@router.post("/dialogue-event", response_model=DirectorProcessResponse)
def post_dialogue_event(payload: DialogueEventRequest) -> DirectorProcessResponse:
    _ensure_enabled()
    return _to_response(_pipeline.process(payload.to_event()))


@router.post("/execute", response_model=ExecuteResponse)
def post_execute(payload: ExecuteRequest) -> ExecuteResponse:
    _ensure_enabled()
    result = _pipeline.execute(
        payload.decision,
        force=payload.force,
        stagger=payload.stagger,
    )
    return ExecuteResponse(
        executed=result.executed,
        blocked_reason=result.blocked_reason,
        osc_commands=result.osc_commands,
    )


@router.post("/osc-test", response_model=OscTestResponse)
def post_osc_test(payload: OscTestRequest | None = None) -> OscTestResponse:
    """Send ping + play_clip to TouchDesigner for wiring checks."""
    _ensure_enabled()
    body = payload or OscTestRequest()
    dry_run = settings.osc_dry_run
    target = f"{settings.osc_host}:{settings.osc_port}"
    bridge = _pipeline.touchdesigner
    bridge._send("/theatermaschine/ping", "hello")
    bridge.play_clip(body.clip_id, opacity=0.8, fade_time=4.0)
    messages = [
        OscCommand(
            bridge="visual",
            host=settings.osc_host,
            port=settings.osc_port,
            address="/theatermaschine/ping",
            args=["hello"],
            dry_run=dry_run,
        ),
        OscCommand(
            bridge="visual",
            host=settings.osc_host,
            port=settings.osc_port,
            address="/visual/play_clip",
            args=[body.clip_id, 0.8, 4.0],
            dry_run=dry_run,
        ),
    ]
    return OscTestResponse(sent=not dry_run, dry_run=dry_run, target=target, messages=messages)


@router.get("/status", response_model=DirectorStatusResponse)
def get_status() -> DirectorStatusResponse:
    _ensure_enabled()
    return _status_response()


@router.patch("/safety", response_model=DirectorStatusResponse)
def patch_safety(payload: SafetyUpdateRequest) -> DirectorStatusResponse:
    _ensure_enabled()
    updates = payload.model_dump(exclude_none=True)
    if updates:
        _pipeline.safety.update(**updates)
    return _status_response()


@router.post("/emergency-stop", response_model=DirectorStatusResponse)
def emergency_stop() -> DirectorStatusResponse:
    _ensure_enabled()
    _pipeline.emergency_stop()
    return _status_response()


@router.post("/emergency-clear", response_model=DirectorStatusResponse)
def emergency_clear() -> DirectorStatusResponse:
    _ensure_enabled()
    _pipeline.safety.clear_emergency_stop()
    return _status_response()


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
                "planned_commands": [c.model_dump(mode="json") for c in result.planned_commands],
                "osc_commands": [c.model_dump(mode="json") for c in result.osc_commands],
                "safety": _pipeline.safety.to_dict(),
                "active_cues": list(_pipeline.scheduler.active_cues),
                "last_osc_commands": [
                    c.model_dump(mode="json") for c in _pipeline.state.last_osc_commands
                ],
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
    return _to_response(result)
