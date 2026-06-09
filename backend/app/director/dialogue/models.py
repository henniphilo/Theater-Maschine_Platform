from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DialogueSpeaker(str, Enum):
    AI_A = "AI_A"
    AI_B = "AI_B"


class DialogueEvent(BaseModel):
    speaker: DialogueSpeaker
    text: str = Field(min_length=1)
    topic: str = ""
    mood: str = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    timestamp: float = 0.0
    created_at: datetime | None = None
