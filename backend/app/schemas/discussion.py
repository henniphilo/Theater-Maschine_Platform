"""Shared workshop discussion types (avoids script ↔ part1_selection import cycle)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.director.cues.cue_models import DramaturgyDecision

DramaturgSpeaker = Literal["openai", "anthropic"]


class DiscussionTurn(BaseModel):
    speaker: DramaturgSpeaker
    content: str = Field(min_length=1)
    proposed_decision: DramaturgyDecision | None = None
