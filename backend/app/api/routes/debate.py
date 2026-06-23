import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_user import get_or_create_local_user
from app.db.session import get_db
from app.models.entities import Conversation, Message
from app.schemas.debate import (
    DebateRequest,
    DebateResponse,
    DebateTurn,
    TTSRequest,
    TTSStatusResponse,
)
from app.api.routes.director import process_debate_turn_if_enabled
from app.services.debate_service import DebateEvent, DebateService, TurnResult
from app.services.tts_service import TTSService

router = APIRouter(prefix="/debate", tags=["debate"])
tts_router = APIRouter(prefix="/tts", tags=["tts"])
debate_service = DebateService()
tts_service = TTSService()


def _extract_topic(messages: list[Message]) -> str:
    for msg in messages:
        if msg.role == "user" and msg.content.startswith("[Debate topic]"):
            return msg.content.removeprefix("[Debate topic]").strip()
    for msg in messages:
        if msg.role == "user":
            return msg.content.strip()
    return "Debate"


def _prior_turns(messages: list[Message]) -> list[TurnResult]:
    turns: list[TurnResult] = []
    for msg in messages:
        if msg.role != "assistant" or msg.provider not in ("openai", "anthropic"):
            continue
        turns.append(
            TurnResult(
                speaker=msg.provider,
                content=msg.content,
                model=msg.model,
                created_at=msg.created_at or datetime.now(UTC),
            )
        )
    return turns


def _get_conversation(db: Session, conversation_id: str, owner_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.owner_id == owner_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _prepare_debate(
    db: Session, payload: DebateRequest
) -> tuple[Conversation, str, list[TurnResult], bool]:
    user = get_or_create_local_user(db)
    prior: list[TurnResult] = []

    if payload.continue_debate:
        if not payload.conversation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="conversation_id required to continue debate",
            )
        conversation = _get_conversation(db, payload.conversation_id, user.id)
        rows = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        ).all()
        topic = _extract_topic(list(rows))
        prior = _prior_turns(list(rows))
        return conversation, topic, prior, False

    if payload.conversation_id:
        conversation = _get_conversation(db, payload.conversation_id, user.id)
        rows = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        ).all()
        prior = _prior_turns(list(rows))
        topic = payload.topic.strip() or _extract_topic(list(rows))
    else:
        if not payload.topic.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topic required")
        title = payload.topic[:70] + ("…" if len(payload.topic) > 70 else "")
        conversation = Conversation(owner_id=user.id, title=f"Debate: {title}")
        db.add(conversation)
        db.flush()
        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=f"[Debate topic] {payload.topic.strip()}",
                provider="system",
                model="debate",
            )
        )
        db.flush()
        topic = payload.topic.strip()

    if not topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topic required")

    return conversation, topic, prior, not prior


def _event_payload(
    event: DebateEvent,
    conversation_id: str | None = None,
    topic: str | None = None,
    director: dict | None = None,
) -> dict:
    data: dict = {"type": event.type}
    if event.speaker:
        data["speaker"] = event.speaker
    if event.content is not None:
        data["content"] = event.content
    if event.model:
        data["model"] = event.model
    if event.created_at:
        data["created_at"] = event.created_at.isoformat()
    if event.detail:
        data["detail"] = event.detail
    if conversation_id:
        data["conversation_id"] = conversation_id
    if topic:
        data["topic"] = topic
    if director:
        data["director"] = director
    return data


async def _stream_debate(
    db: Session,
    conversation: Conversation,
    topic: str,
    payload: DebateRequest,
    prior: list[TurnResult],
) -> AsyncIterator[str]:
    try:
        async for event in debate_service.run_stream(
            topic=topic,
            rounds=payload.rounds,
            openai_model=payload.openai_model,
            anthropic_model=payload.anthropic_model,
            prior_turns=prior,
        ):
            director_payload = None
            if event.type == "turn" and event.content and event.speaker and event.model:
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=event.content,
                        provider=event.speaker,
                        model=event.model,
                    )
                )
                db.commit()

                director_result = process_debate_turn_if_enabled(
                    speaker=event.speaker,
                    text=event.content,
                    topic=topic,
                    created_at=event.created_at,
                )
                if director_result is not None:
                    director_payload = director_result.model_dump(mode="json")

            if event.type == "done":
                yield f"data: {json.dumps(_event_payload(event, conversation.id, topic))}\n\n"
            elif event.type == "error":
                yield f"data: {json.dumps(_event_payload(event))}\n\n"
            elif event.type == "turn":
                yield f"data: {json.dumps(_event_payload(event, conversation.id, topic, director_payload))}\n\n"
            else:
                yield f"data: {json.dumps(_event_payload(event))}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id, 'topic': topic})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"


@router.post("/stream")
async def stream_debate(payload: DebateRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    conversation, topic, prior, _ = _prepare_debate(db, payload)
    return StreamingResponse(
        _stream_debate(db, conversation, topic, payload, prior),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", response_model=DebateResponse)
async def start_debate(payload: DebateRequest, db: Session = Depends(get_db)) -> DebateResponse:
    conversation, topic, prior, _ = _prepare_debate(db, payload)
    try:
        results = await debate_service.run(
            topic=topic,
            rounds=payload.rounds,
            openai_model=payload.openai_model,
            anthropic_model=payload.anthropic_model,
            prior_turns=prior,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    response_turns: list[DebateTurn] = []
    for turn in results:
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=turn.content,
                provider=turn.speaker,
                model=turn.model,
            )
        )
        response_turns.append(
            DebateTurn(
                speaker=turn.speaker,
                content=turn.content,
                model=turn.model,
                created_at=turn.created_at,
            )
        )
    db.commit()

    return DebateResponse(conversation_id=conversation.id, topic=topic, turns=response_turns)


@tts_router.get("/status", response_model=TTSStatusResponse)
def tts_status() -> TTSStatusResponse:
    try:
        provider = tts_service.resolve_provider()
        openai_voice, anthropic_voice, narrator_voice = tts_service.voice_labels()
        available = True
        hint = tts_service.status_hint()
    except RuntimeError as exc:
        provider = "none"
        openai_voice = ""
        anthropic_voice = ""
        narrator_voice = ""
        available = False
        hint = str(exc)

    return TTSStatusResponse(
        available=available,
        platform=tts_service.platform,
        provider=provider,
        hint=hint,
        openai_voice=openai_voice,
        anthropic_voice=anthropic_voice,
        narrator_voice=narrator_voice,
    )


@tts_router.get("/voices")
async def tts_voices() -> dict[str, list[str]]:
    try:
        return {"voices": await tts_service.list_voices()}
    except RuntimeError:
        return {"voices": []}


@tts_router.post("/speak")
async def tts_speak(payload: TTSRequest) -> FileResponse:
    try:
        spoken = payload.text.strip()
        audio_path = await tts_service.synthesize(
            spoken,
            payload.speaker,
            profile=payload.profile,  # type: ignore[arg-type]
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    media_map = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".aiff": "audio/aiff"}
    media = media_map.get(audio_path.suffix, "application/octet-stream")
    return FileResponse(audio_path, media_type=media, filename=audio_path.name)
