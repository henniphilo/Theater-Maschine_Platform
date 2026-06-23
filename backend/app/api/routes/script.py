import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import ValidationError

from app.director.cues.cue_models import DramaturgyDecision, OscCommand
from app.director.outputs.part1_logger import get_part1_logger
from app.schemas.script import (
    CreateScriptRequest,
    DiscussionTurn,
    DramaturgyStreamRequest,
    PatchScriptBeatRequest,
    PatchScriptRequest,
    ProductionScript,
)
from app.services.baerenklau_beat import resolve_part1_beats
from app.services.dramaturg_labels import dramaturg_display_name
from app.services.part1_selection_store import get_part1_selection_store
from app.services.part1_workshop_service import Part1WorkshopService
from app.services.performance_bundle_service import get_performance_bundle_service
from app.services.script_splitter import build_part1_whole_beat
from app.services.script_store import get_script_store

router = APIRouter(prefix="/scripts", tags=["scripts"])
_store = get_script_store()
_workshop = Part1WorkshopService()
_selection_store = get_part1_selection_store()
_performance = get_performance_bundle_service()
_part1_log = get_part1_logger()


@router.post("", response_model=ProductionScript, status_code=status.HTTP_201_CREATED)
def create_script(payload: CreateScriptRequest) -> ProductionScript:
    beats = build_part1_whole_beat(payload.source_text)
    if not beats:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty script text")
    return _store.create(payload.title, payload.source_text, beats)


@router.get("/{script_id}", response_model=ProductionScript)
def get_script(script_id: str) -> ProductionScript:
    script = _store.get(script_id)
    return _selection_store.attach_to_script(script)


@router.patch("/{script_id}", response_model=ProductionScript)
def patch_script(script_id: str, payload: PatchScriptRequest) -> ProductionScript:
    return _store.patch_script(script_id, payload)


@router.patch("/{script_id}/beats/{beat_id}", response_model=ProductionScript)
def patch_beat(script_id: str, beat_id: str, payload: PatchScriptBeatRequest) -> ProductionScript:
    return _store.patch_beat(script_id, beat_id, payload)


def _workshop_payload(event) -> dict:
    data: dict = {"type": event.type}
    if event.beat_id is not None:
        data["beat_id"] = event.beat_id
    if event.beat_order is not None:
        data["beat_order"] = event.beat_order
    if event.speaker is not None:
        data["speaker"] = event.speaker
        data["speaker_label"] = dramaturg_display_name(event.speaker)
    if event.content is not None:
        data["content"] = event.content
    if event.dramaturgy is not None:
        data["dramaturgy"] = event.dramaturgy
    if event.planned_commands is not None:
        data["planned_commands"] = event.planned_commands
    if event.discussion_summary is not None:
        data["discussion_summary"] = event.discussion_summary
    if event.discussion_turns is not None:
        data["discussion_turns"] = event.discussion_turns
    if event.preview is not None:
        data["preview"] = event.preview
    if event.media_selection is not None:
        data["media_selection"] = event.media_selection
    if event.part1_selection is not None:
        data["part1_selection"] = event.part1_selection
    if event.workshop_phase is not None:
        data["workshop_phase"] = event.workshop_phase
    if event.detail is not None:
        data["detail"] = event.detail
    return data


async def _dramaturgy_stream(script_id: str, payload: DramaturgyStreamRequest) -> AsyncIterator[str]:
    script = _store.get(script_id)
    part1_beats = resolve_part1_beats(script.beats)
    if not part1_beats:
        yield f"data: {json.dumps({'type': 'error', 'detail': 'Kein Stücktext — bitte Text eingeben'})}\n\n"
        return

    beat = part1_beats[0]
    _part1_log.log("workshop_start", script_id=script_id, beat_count=1)
    try:
        async for event in _workshop.run_stream(
            script_id=script_id,
            title=script.title,
            beat=beat,
            openai_model=payload.openai_model,
            anthropic_model=payload.anthropic_model,
        ):
            if event.type == "discussion_turn" and event.beat_id and event.discussion_turns:
                existing = next((b for b in script.beats if b.id == event.beat_id), None)
                if existing:
                    existing.discussion_turns = [
                        DiscussionTurn.model_validate(t) for t in event.discussion_turns
                    ]
                    script = _store.update_beat(script_id, existing)

            if event.type == "preview_start" and event.preview:
                _part1_log.log(
                    "preview_start",
                    medium=event.preview.get("medium"),
                    medium_id=event.preview.get("medium_id"),
                )

            if event.type == "preview_end" and event.preview:
                _part1_log.log(
                    "preview_end",
                    medium=event.preview.get("medium"),
                    medium_id=event.preview.get("medium_id"),
                )

            if event.type == "agreement_saved" and event.part1_selection:
                from app.schemas.part1_selection import Part1BaerenklauSelection

                selection = Part1BaerenklauSelection.model_validate(event.part1_selection)
                _selection_store.save(selection)
                script = _store.get(script_id)
                _part1_log.log("agreement_saved", script_id=script_id)

            if event.type == "dramaturgy_decision" and event.beat_id and event.dramaturgy:
                existing = next((b for b in script.beats if b.id == event.beat_id), None)
                if existing:
                    existing.dramaturgy = DramaturgyDecision.model_validate(event.dramaturgy)
                    existing.planned_commands = [
                        OscCommand.model_validate(c) for c in (event.planned_commands or [])
                    ]
                    if event.discussion_turns:
                        existing.discussion_turns = [
                            DiscussionTurn.model_validate(t) for t in event.discussion_turns
                        ]
                    existing.discussion_summary = event.discussion_summary
                    script = _store.update_beat(script_id, existing)

            yield f"data: {json.dumps(_workshop_payload(event))}\n\n"

        script = _store.get(script_id)
        script = _selection_store.attach_to_script(script)
        if script.part1_selection is None and script.status == "ready":
            script.performance_part = script.performance_part or "part1_baerenklau"
            _store.save(script)
        yield f"data: {json.dumps({'type': 'script_updated', 'script': script.model_dump(mode='json')})}\n\n"
        _part1_log.log("workshop_done", script_id=script_id, title=script.title)
        print(f"[Theatermaschine] Dramaturgen-Workshop abgeschlossen — script_id={script_id} title={script.title!r}")
    except ValidationError as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"


@router.post("/{script_id}/dramaturgy/stream")
async def stream_dramaturgy(script_id: str, payload: DramaturgyStreamRequest) -> StreamingResponse:
    _store.get(script_id)
    return StreamingResponse(
        _dramaturgy_stream(script_id, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{script_id}/performance/export")
async def export_performance(script_id: str) -> Response:
    await _performance.render_and_save(script_id)
    data, filename = _performance.build_zip_bytes(script_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{script_id}/performance/download")
def download_performance(script_id: str) -> Response:
    _store.get(script_id)
    data, filename = _performance.build_zip_bytes(script_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/performance/import", response_model=ProductionScript, status_code=status.HTTP_201_CREATED)
async def import_performance(file: UploadFile = File(...)) -> ProductionScript:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded")
    data = await file.read()
    return _performance.import_zip(data)


@router.get("/{script_id}/performance/audio/{beat_id}/{asset}")
def get_performance_audio(script_id: str, beat_id: str, asset: str) -> FileResponse:
    _store.get(script_id)
    path = _performance.audio_path(script_id, beat_id, asset)
    media = "audio/mpeg" if path.suffix.lower() in {".mp3", ".m4a"} else "audio/aiff"
    return FileResponse(path, media_type=media)
