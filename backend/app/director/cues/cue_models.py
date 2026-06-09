from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VisualAction(str, Enum):
    PLAY_CLIP = "play_clip"
    STOP_CLIP = "stop_clip"
    RECORD_LIVE = "record_live"
    PLAY_RECORDING = "play_recording"
    FADE_TO_BLACK = "fade_to_black"


class SoundAction(str, Enum):
    TRIGGER_CUE = "trigger_cue"
    STOP_CUE = "stop_cue"
    SET_VOLUME = "set_volume"


class LightAction(str, Enum):
    SET_SCENE = "set_scene"
    FADE_BLACKOUT = "fade_blackout"
    PULSE = "pulse"


class VisualCue(BaseModel):
    action: VisualAction = VisualAction.PLAY_CLIP
    clip_id: str | None = None
    recording_id: str | None = None
    blend: str = "slow_fade"
    opacity: float = Field(default=0.8, ge=0.0, le=1.0)
    fade_time: float = Field(default=4.0, ge=0.0)


class SoundCue(BaseModel):
    action: SoundAction = SoundAction.TRIGGER_CUE
    cue_id: str | None = None
    volume: float = Field(default=0.6, ge=0.0, le=1.0)


class LightCue(BaseModel):
    action: LightAction = LightAction.SET_SCENE
    scene_id: str | None = None
    fade_time: float = Field(default=4.0, ge=0.0)


class DramaturgyDecision(BaseModel):
    visual: VisualCue | None = None
    sound: SoundCue | None = None
    light: LightCue | None = None
    reason: str = ""
    tags: list[str] = Field(default_factory=list)
    mood: str = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    timestamp: float = 0.0


class ScheduledCue(BaseModel):
    decision: DramaturgyDecision
    scheduled_at: datetime
    executed: bool = False
    blocked_reason: str | None = None
