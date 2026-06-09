from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_user import get_or_create_local_user
from app.db.session import get_db
from app.models.entities import Conversation, Message
from app.schemas.conversation import ConversationItem, MessageItem

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationItem])
def list_conversations(
    db: Session = Depends(get_db),
) -> list[ConversationItem]:
    user = get_or_create_local_user(db)
    rows = db.scalars(
        select(Conversation).where(Conversation.owner_id == user.id).order_by(Conversation.created_at.desc())
    ).all()
    return [ConversationItem(id=row.id, title=row.title, created_at=row.created_at) for row in rows]


@router.get("/{conversation_id}/messages", response_model=list[MessageItem])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> list[MessageItem]:
    user = get_or_create_local_user(db)
    conversation = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.owner_id == user.id)
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    ).all()
    return [
        MessageItem(
            id=row.id,
            role=row.role,
            content=row.content,
            provider=row.provider,
            model=row.model,
            created_at=row.created_at,
        )
        for row in rows
    ]
