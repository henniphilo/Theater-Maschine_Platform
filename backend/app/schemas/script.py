from typing import Literal

from pydantic import BaseModel, Field

from app.director.cues.cue_models import DramaturgyDecision, OscCommand

ScriptSpeaker = Literal["AI_A", "AI_B", "narrator"]
ScriptStatus = Literal["draft", "review", "ready"]


class ScriptBeat(BaseModel):
    id: str
    order: int
    text: str
    speaker: ScriptSpeaker = "AI_A"
    dramaturgy: DramaturgyDecision | None = None
    planned_commands: list[OscCommand] = Field(default_factory=list)
    discussion_summary: str | None = None


class ProductionScript(BaseModel):
    id: str
    title: str
    source_text: str
    beats: list[ScriptBeat] = Field(default_factory=list)
    status: ScriptStatus = "draft"


class CreateScriptRequest(BaseModel):
    title: str = Field(default="Stück", max_length=200)
    source_text: str = Field(min_length=1, max_length=50000)


class PatchScriptBeatRequest(BaseModel):
    speaker: ScriptSpeaker | None = None
    dramaturgy: DramaturgyDecision | None = None


class DramaturgyStreamRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o", min_length=3, max_length=80)
    anthropic_model: str = Field(default="claude-sonnet-4-6", min_length=3, max_length=80)
    discussion_rounds: int = Field(default=3, ge=1, le=6)
