from datetime import datetime

from pydantic import BaseModel, Field


class DebateRequest(BaseModel):
    topic: str = Field(default="", max_length=4000)
    rounds: int = Field(default=3, ge=1, le=8)
    openai_model: str = Field(default="gpt-4o", min_length=3, max_length=80)
    anthropic_model: str = Field(default="claude-sonnet-4-6", min_length=3, max_length=80)
    conversation_id: str | None = None
    continue_debate: bool = False


class DebateTurn(BaseModel):
    speaker: str
    content: str
    model: str
    created_at: datetime


class DebateResponse(BaseModel):
    conversation_id: str
    topic: str
    turns: list[DebateTurn]


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    speaker: str = Field(pattern="^(openai|anthropic|AI_A|AI_B|narrator)$")
    profile: str | None = Field(
        default=None,
        pattern="^(dramaturg|performance|inszenierung)$",
    )


class TTSStatusResponse(BaseModel):
    available: bool
    platform: str
    provider: str
    hint: str
    openai_voice: str
    anthropic_voice: str
    narrator_voice: str = ""
