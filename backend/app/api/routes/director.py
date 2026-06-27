import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.director.pipeline import get_director_pipeline
from app.director.recording import RecordingManager
from app.schemas.director import (
    DialogueEventRequest,
    DirectorProcessResponse,
    DirectorStatusResponse,
    ExecuteRequest,
    ExecuteLayeredRequest,
    ExecuteResponse,
    OscTestRequest,
    OscTestResponse,
    RecordingRequest,
    RecordingStatusResponse,
    SafetyUpdateRequest,
    TechnikHoldStatusResponse,
    TechnikStopRequest,
    LightDeskStatusResponse,
    LightSendRequest,
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


@router.post("/execute-layered", response_model=ExecuteResponse)
def post_execute_layered(payload: ExecuteLayeredRequest) -> ExecuteResponse:
    _ensure_enabled()
    result = _pipeline.execute_layered(
        payload.decision,
        anarchy_level=payload.anarchy_level,
        stack=payload.stack,
        skip_interval_check=payload.skip_interval_check,
        stagger=payload.stagger,
        text_excerpt=payload.text_excerpt,
    )
    return ExecuteResponse(
        executed=result.executed,
        blocked_reason=result.blocked_reason,
        osc_commands=result.osc_commands,
    )


@router.post("/osc-test", response_model=OscTestResponse)
def post_osc_test(payload: OscTestRequest | None = None) -> OscTestResponse:
    """Send selected OSC test signals (video, sound, light) like performance execute."""
    _ensure_enabled()
    from app.director.cues.cue_models import (
        DramaturgyDecision,
        LightCue,
        SoundAction,
        SoundCue,
        VisualAction,
        VisualCue,
    )
    from app.director.media.database import MediaDatabase

    body = payload or OscTestRequest()
    db = MediaDatabase()
    video_ids = {v.id for v in db.videos}
    sound_ids = {s.id for s in db.sounds}
    light_ids = {s.id for s in db.light_scenes}

    if body.send_visual and body.clip_id not in video_ids:
        raise HTTPException(status_code=400, detail=f"Unknown clip_id: {body.clip_id}")
    if body.send_sound and body.sound_cue_id not in sound_ids:
        raise HTTPException(status_code=400, detail=f"Unknown sound_cue_id: {body.sound_cue_id}")
    if body.send_light and body.light_scene_id not in light_ids:
        raise HTTPException(status_code=400, detail=f"Unknown light_scene_id: {body.light_scene_id}")

    if not body.send_visual and not body.send_sound and not body.send_light:
        raise HTTPException(status_code=400, detail="At least one of send_visual, send_sound, send_light required")

    decision = DramaturgyDecision(
        visual=(
            VisualCue(
                action=VisualAction.PLAY_CLIP,
                clip_id=body.clip_id,
                opacity=body.opacity,
                fade_time=body.fade_time,
            )
            if body.send_visual
            else None
        ),
        sound=(
            SoundCue(
                action=SoundAction.TRIGGER_CUE,
                cue_id=body.sound_cue_id,
                volume=body.volume,
            )
            if body.send_sound
            else None
        ),
        light=(
            LightCue(scene_id=body.light_scene_id, fade_time=body.fade_time)
            if body.send_light
            else None
        ),
        reason="OSC Technik-Test",
    )
    result = _pipeline.execute(decision, force=True, stagger=body.stagger)
    dry_run = settings.osc_dry_run
    target = f"{settings.osc_host}:{settings.osc_port}"
    return OscTestResponse(
        sent=not dry_run and result.executed,
        dry_run=dry_run,
        target=target,
        executed=result.executed,
        blocked_reason=result.blocked_reason,
        messages=result.osc_commands,
    )


def _technik_state_from_request(body: OscTestRequest):
    from app.director.technik_hold import TechnikHoldState

    return TechnikHoldState(
        clip_id=body.clip_id,
        sound_cue_id=body.sound_cue_id,
        light_scene_id=body.light_scene_id,
        send_visual=body.send_visual,
        send_sound=body.send_sound,
        send_light=body.send_light,
        opacity=body.opacity,
        volume=body.volume,
    )


def _technik_status_response() -> TechnikHoldStatusResponse:
    from app.director.technik_hold import get_technik_hold_manager

    state = get_technik_hold_manager(_pipeline).status()
    if state is None:
        return TechnikHoldStatusResponse(active=False)
    return TechnikHoldStatusResponse(
        active=True,
        send_visual=state.send_visual,
        send_sound=state.send_sound,
        send_light=state.send_light,
        clip_id=state.clip_id if state.send_visual else None,
        sound_cue_id=state.sound_cue_id if state.send_sound else None,
        light_scene_id=state.light_scene_id if state.send_light else None,
    )


@router.post("/technik/start", response_model=TechnikHoldStatusResponse)
def post_technik_start(payload: OscTestRequest | None = None) -> TechnikHoldStatusResponse:
    """Start sustained Technik output (hold keepalives until stop)."""
    _ensure_enabled()
    from app.director.media.database import MediaDatabase
    from app.director.technik_hold import get_technik_hold_manager

    body = payload or OscTestRequest()
    db = MediaDatabase()
    if body.send_visual and body.clip_id not in {v.id for v in db.videos}:
        raise HTTPException(status_code=400, detail=f"Unknown clip_id: {body.clip_id}")
    if body.send_sound and body.sound_cue_id not in {s.id for s in db.sounds}:
        raise HTTPException(status_code=400, detail=f"Unknown sound_cue_id: {body.sound_cue_id}")
    if body.send_light and body.light_scene_id not in {s.id for s in db.light_scenes}:
        raise HTTPException(status_code=400, detail=f"Unknown light_scene_id: {body.light_scene_id}")
    if not body.send_visual and not body.send_sound and not body.send_light:
        raise HTTPException(status_code=400, detail="At least one of send_visual, send_sound, send_light required")
    if body.send_light:
        raise HTTPException(
            status_code=400,
            detail="Light uses two-step test: POST /director/light/connect then /director/light/send",
        )

    get_technik_hold_manager(_pipeline).start(_technik_state_from_request(body))
    return _technik_status_response()


@router.post("/technik/stop", response_model=TechnikHoldStatusResponse)
def post_technik_stop(payload: TechnikStopRequest | None = None) -> TechnikHoldStatusResponse:
    """Stop sustained Technik output (per channel or all)."""
    _ensure_enabled()
    from app.director.technik_hold import get_technik_hold_manager

    body = payload or TechnikStopRequest()
    get_technik_hold_manager(_pipeline).stop(
        send_visual=body.send_visual,
        send_sound=body.send_sound,
        send_light=body.send_light,
    )
    return _technik_status_response()


@router.get("/technik/status", response_model=TechnikHoldStatusResponse)
def get_technik_status() -> TechnikHoldStatusResponse:
    _ensure_enabled()
    return _technik_status_response()


def _light_desk_status_response() -> LightDeskStatusResponse:
    from app.director.light_desk_test import get_light_desk_test_manager

    status = get_light_desk_test_manager(_pipeline).status()
    return LightDeskStatusResponse(
        tcp_connected=status.tcp_connected,
        scene_id=status.scene_id,
        hold_active=status.hold_active,
        intensity=status.intensity,
    )


@router.post("/light/connect", response_model=LightDeskStatusResponse)
def post_light_connect() -> LightDeskStatusResponse:
    _ensure_enabled()
    from app.director.light_desk_test import get_light_desk_test_manager

    status = get_light_desk_test_manager(_pipeline).connect()
    return _light_desk_status_response_from(status)


@router.post("/light/disconnect", response_model=LightDeskStatusResponse)
def post_light_disconnect() -> LightDeskStatusResponse:
    _ensure_enabled()
    from app.director.light_desk_test import get_light_desk_test_manager

    status = get_light_desk_test_manager(_pipeline).disconnect()
    return _light_desk_status_response_from(status)


@router.get("/light/status", response_model=LightDeskStatusResponse)
def get_light_status() -> LightDeskStatusResponse:
    _ensure_enabled()
    return _light_desk_status_response()


@router.post("/light/send", response_model=LightDeskStatusResponse)
def post_light_send(payload: LightSendRequest) -> LightDeskStatusResponse:
    _ensure_enabled()
    from app.director.light_desk_test import LightDeskNotConnectedError, get_light_desk_test_manager
    from app.director.media.database import MediaDatabase

    if payload.light_scene_id not in {s.id for s in MediaDatabase().light_scenes}:
        raise HTTPException(status_code=400, detail=f"Unknown light_scene_id: {payload.light_scene_id}")
    try:
        status = get_light_desk_test_manager(_pipeline).send_scene(
            payload.light_scene_id,
            intensity=payload.intensity,
        )
    except LightDeskNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _light_desk_status_response_from(status)


@router.post("/light/hold/start", response_model=LightDeskStatusResponse)
def post_light_hold_start(payload: LightSendRequest) -> LightDeskStatusResponse:
    _ensure_enabled()
    from app.director.light_desk_test import LightDeskNotConnectedError, get_light_desk_test_manager
    from app.director.media.database import MediaDatabase

    if payload.light_scene_id not in {s.id for s in MediaDatabase().light_scenes}:
        raise HTTPException(status_code=400, detail=f"Unknown light_scene_id: {payload.light_scene_id}")
    try:
        status = get_light_desk_test_manager(_pipeline).start_hold(
            payload.light_scene_id,
            intensity=payload.intensity,
        )
    except LightDeskNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _light_desk_status_response_from(status)


@router.post("/light/stop", response_model=LightDeskStatusResponse)
def post_light_stop() -> LightDeskStatusResponse:
    _ensure_enabled()
    from app.director.light_desk_test import get_light_desk_test_manager

    status = get_light_desk_test_manager(_pipeline).stop_signal()
    return _light_desk_status_response_from(status)


def _light_desk_status_response_from(status) -> LightDeskStatusResponse:
    return LightDeskStatusResponse(
        tcp_connected=status.tcp_connected,
        scene_id=status.scene_id,
        hold_active=status.hold_active,
        intensity=status.intensity,
    )


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
    _pipeline.clear_for_performance()
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
