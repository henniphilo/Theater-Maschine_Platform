from typing import Literal

from pydantic import BaseModel, Field

from app.director.cues.cue_models import DramaturgyDecision, OscCommand
from app.schemas.discussion import DiscussionTurn
from app.schemas.part1_selection import Part1BaerenklauSelection, PerformancePart

ScriptSpeaker = Literal["AI_A", "AI_B", "narrator"]
ScriptStatus = Literal["draft", "review", "ready"]


class ScriptBeat(BaseModel):
    id: str
    order: int
    text: str
    scene_title: str | None = None
    speaker: ScriptSpeaker = "AI_A"
    dramaturgy: DramaturgyDecision | None = None
    planned_commands: list[OscCommand] = Field(default_factory=list)
    discussion_turns: list[DiscussionTurn] = Field(default_factory=list)
    discussion_summary: str | None = None


class ProductionScript(BaseModel):
    id: str
    title: str
    source_text: str
    beats: list[ScriptBeat] = Field(default_factory=list)
    status: ScriptStatus = "draft"
    has_rendered_audio: bool = False
    part1_selection: Part1BaerenklauSelection | None = None
    performance_part: PerformancePart | None = None
    teil2_corpus_id: str | None = None


class CreateScriptRequest(BaseModel):
    title: str = Field(default="Stück", max_length=200)
    source_text: str = Field(min_length=1, max_length=50000)


class PatchScriptBeatRequest(BaseModel):
    speaker: ScriptSpeaker | None = None
    dramaturgy: DramaturgyDecision | None = None


class PatchScriptRequest(BaseModel):
    performance_part: PerformancePart | None = None
    teil2_corpus_id: str | None = Field(default=None, max_length=80)


class DramaturgyStreamRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o", min_length=3, max_length=80)
    anthropic_model: str = Field(default="claude-sonnet-4-6", min_length=3, max_length=80)
    discussion_rounds: int = Field(default=1, ge=0, le=3)
