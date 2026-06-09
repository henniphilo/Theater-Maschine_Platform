from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=12000)
    provider: str = Field(pattern="^(openai|anthropic)$")
    model: str = Field(min_length=3, max_length=80)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    provider: str
    model: str
    created_at: datetime
