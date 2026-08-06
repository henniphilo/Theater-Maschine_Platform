from typing import Literal

from pydantic import BaseModel, Field

from app.director.cues.cue_models import (
    CuePoint,
    DramaturgyDecision,
    PerformanceSpeaker,
    VisualCue,
    VisualOutputAssignment,
)

InszenierungStatus = Literal["draft", "analyzed", "composed", "preparing", "ready"]
CueAnnotationKind = Literal["light", "sound", "video", "avatar", "space"]
SpeechMode = Literal["tts", "avatar_video", "silent"]
ScriptSource = Literal["avatar_delfin_wolf"]
ProjectorMode = Literal["single", "all"]


class AnimalPosition(BaseModel):
    animal: str
    stance: str = ""
    money_angle: str = ""


class CrossSceneLink(BaseModel):
    label: str
    scene_ids: list[str] = Field(default_factory=list)
    note: str = ""


class AnarchyCurve(BaseModel):
    start: float = Field(default=0.35, ge=0.0, le=1.0)
    end: float = Field(default=1.0, ge=0.0, le=1.0)


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


class AvatarSpeechLayer(BaseModel):
    avatar_speech_id: str
    avatar: str
    video_clip_id: str
    projector: str | None = None
    outputs: list[VisualOutputAssignment] = Field(default_factory=list)
    visual_cue: VisualCue | None = None


class CompositionMoment(BaseModel):
    id: str
    order: int
    scene_id: str
    text_excerpt: str = Field(min_length=1)
    speaker: PerformanceSpeaker = "AI_A"
    speech_mode: SpeechMode = "tts"
    avatar_speech_id: str | None = None
    avatar_video_clip_id: str | None = None
    avatar_layers: list[AvatarSpeechLayer] = Field(default_factory=list)
    projector_mode: ProjectorMode = "single"
    avatar_video_cue: VisualCue | None = None
    atmosphere_video_cues: list[VisualCue] = Field(default_factory=list)
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


class AvatarTextSegment(BaseModel):
    csv_cue_ids: list[str] = Field(default_factory=list)
    text_excerpt: str = Field(min_length=1)
    char_offset: int | None = Field(default=None, ge=0)
    csv_sequence_index: int = Field(default=0, ge=0)
    start_sentence_index: int = Field(ge=0)
    end_sentence_index: int = Field(ge=0)
    avatar_layers: list[AvatarSpeechLayer] = Field(default_factory=list)


class CueAnnotation(BaseModel):
    kind: CueAnnotationKind
    label: str
    projector: str | None = None
    time_sec: float | None = None
    sentence_index: int | None = None
    reason: str | None = None


class ScriptCueRow(BaseModel):
    sentence_index: int = Field(ge=0)
    text: str
    annotations: list[CueAnnotation] = Field(default_factory=list)


class ScriptCueOverview(BaseModel):
    rows: list[ScriptCueRow] = Field(default_factory=list)
    atmosphere_timeline: list[CueAnnotation] = Field(default_factory=list)


class Teil2PerformancePlan(BaseModel):
    performance_speaker: PerformanceSpeaker = "narrator"
    sentences: list[str] = Field(default_factory=list)
    sentence_char_starts: list[int] = Field(default_factory=list)
    avatar_segments: list[AvatarTextSegment] = Field(default_factory=list)
    dramaturgy: DramaturgyDecision
    atmosphere_cue_points: list[CuePoint] = Field(default_factory=list)
    cue_overview: ScriptCueOverview | None = None
    anarchy_level_end: float = Field(default=1.0, ge=0.0, le=1.0)
    alignment_warnings: list[str] = Field(default_factory=list)


class SceneCorpus(BaseModel):
    id: str
    title: str
    scenes: list[AnimalScene] = Field(default_factory=list)
    script_source: ScriptSource | None = None
    script_text: str | None = None
    status: InszenierungStatus = "draft"
    prepare_phase: str | None = None
    prepare_error: str | None = None
    gesamtkonzept: Gesamtkonzept | None = None
    composition: CompositionPlan | None = None
    teil2_plan: Teil2PerformancePlan | None = None


class ScriptBeatPreview(BaseModel):
    order: int
    text: str
    avatar_ids: list[str] = Field(default_factory=list)
    avatars: list[str] = Field(default_factory=list)
    is_chorus: bool = False


class Teil2ScriptResponse(BaseModel):
    script_source: ScriptSource
    text: str
    beat_count: int
    beats_preview: list[ScriptBeatPreview] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


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
    script_text: str | None = Field(default=None, max_length=500_000)


class PrepareCorpusRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o-mini", min_length=3, max_length=80)
    performance_speaker: PerformanceSpeaker = "narrator"


class AnalyseStreamRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o-mini", min_length=3, max_length=80)
    anthropic_model: str = Field(default="claude-sonnet-4-6", min_length=3, max_length=80)


class KompositionStreamRequest(BaseModel):
    openai_model: str = Field(default="gpt-4o", min_length=3, max_length=80)
    moment_count: int = Field(default=12, ge=4, le=24)
