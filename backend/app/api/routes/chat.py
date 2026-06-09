from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_user import get_or_create_local_user
from app.db.session import get_db
from app.models.entities import Conversation, Message
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import AIService

router = APIRouter(prefix="/chat", tags=["chat"])
ai_service = AIService()


@router.post("", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    user = get_or_create_local_user(db)
    if payload.conversation_id:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id, Conversation.owner_id == user.id
            )
        )
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    else:
        conversation = Conversation(owner_id=user.id, title=payload.message[:70] or "New Chat")
        db.add(conversation)
        db.flush()

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
        provider=payload.provider,
        model=payload.model,
    )
    db.add(user_msg)
    db.flush()

    history_rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
    ).all()
    messages = [{"role": "system", "content": "You are a concise and helpful AI assistant."}]
    messages.extend({"role": row.role, "content": row.content} for row in history_rows)

    try:
        reply = await ai_service.generate(payload.provider, payload.model, messages)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    ai_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
        provider=payload.provider,
        model=payload.model,
    )
    db.add(ai_msg)
    db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply,
        provider=payload.provider,
        model=payload.model,
        created_at=datetime.now(UTC),
    )
