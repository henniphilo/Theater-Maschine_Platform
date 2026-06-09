from datetime import datetime

from pydantic import BaseModel


class ConversationItem(BaseModel):
    id: str
    title: str
    created_at: datetime


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    provider: str
    model: str
    created_at: datetime
