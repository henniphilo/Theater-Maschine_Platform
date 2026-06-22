from typing import Literal

from pydantic import BaseModel, Field

from app.director.cues.cue_models import DramaturgyDecision, PerformanceSpeaker

InszenierungStatus = Literal["draft", "analyzed", "composed", "ready"]


class AnimalPosition(BaseModel):
    animal: str
    stance: str = ""
    money_angle: str = ""


class CrossSceneLink(BaseModel):
    label: str
    scene_ids: list[str] = Field(default_factory=list)
    note: str = ""


class AnarchyCurve(BaseModel):
    start: float = Field(default=0.2, ge=0.0, le=1.0)
    end: float = Field(default=0.95, ge=0.0, le=1.0)


class Gesamtkonzept(BaseModel):
    thesis: str = ""
    money_themes: list[str] = Field(default_factory=list)
    animal_positions: list[AnimalPosition] = Field(default_factory=list)
    cross_scene_links: list[CrossSceneLink] = Field(default_factory=list)
    anarchy_curve: AnarchyCurve = Field(default_factory=AnarchyCurve)
    discussion_summary: str | None = None


class AnimalScene(BaseModel):
    id: str
    animal: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=300)
    source_text: str = Field(min_length=1, max_length=50000)
    play_reference: str | None = None


class CompositionMoment(BaseModel):
    id: str
    order: int
    scene_id: str
    text_excerpt: str = Field(min_length=1)
    speaker: PerformanceSpeaker = "AI_A"
    dramaturgy: DramaturgyDecision | None = None
    overlap_with_previous: float = Field(default=0.0, ge=0.0, le=1.0)
    anarchy_level: float = Field(default=0.2, ge=0.0, le=1.0)
    start_delay_ms: int = Field(default=0, ge=0)
    duration_hint_ms: int | None = Field(default=None, ge=0)


class CompositionPlan(BaseModel):
    moments: list[CompositionMoment] = Field(default_factory=list)
    total_estimated_duration_sec: float = Field(default=0.0, ge=0.0)
    max_concurrent_voices: int = Field(default=3, ge=1, le=6)
    max_concurrent_videos: int = Field(default=2, ge=1, le=6)


class SceneCorpus(BaseModel):
    id: str
    title: str
    scenes: list[AnimalScene] = Field(default_factory=list)
    status: InszenierungStatus = "draft"
    gesamtkonzept: Gesamtkonzept | None = None
    composition: CompositionPlan | None = None


class CreateCorpusRequest(BaseModel):
    title: str = Field(default="Unter Tieren — Geld", max_length=200)


class CreateAnimalSceneRequest(BaseModel):
    animal: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=300)
    source_text: str = Field(min_length=1, max_length=50000)
    play_reference: str | None = None


class BatchAnimalScenesRequest(BaseModel):
    scenes: list[CreateAnimalSceneRequest] = Field(min_length=1, max_length=50)


class PatchCorpusRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class AnalyseStreamRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o", min_length=3, max_length=80)
    anthropic_model: str = Field(default="claude-sonnet-4-6", min_length=3, max_length=80)


class KompositionStreamRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o", min_length=3, max_length=80)
    moment_count: int = Field(default=12, ge=4, le=24)
