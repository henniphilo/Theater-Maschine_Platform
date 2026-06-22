from pydantic import BaseModel, Field

from app.director.cues.cue_models import DramaturgyDecision, OscCommand
from app.director.dialogue.models import DialogueEvent, DialogueSpeaker


class DialogueEventRequest(BaseModel):
    speaker: DialogueSpeaker
    text: str = Field(min_length=1)
    topic: str = ""
    mood: str = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    timestamp: float = 0.0

    def to_event(self) -> DialogueEvent:
        return DialogueEvent(
            speaker=self.speaker,
            text=self.text,
            topic=self.topic,
            mood=self.mood,
            intensity=self.intensity,
            tags=self.tags,
            timestamp=self.timestamp,
        )


class SafetyUpdateRequest(BaseModel):
    autopilot_enabled: bool | None = None
    visuals_enabled: bool | None = None
    sound_enabled: bool | None = None
    lights_enabled: bool | None = None
    blackout_locked: bool | None = None


class DirectorProcessResponse(BaseModel):
    event: DialogueEvent
    decision: DramaturgyDecision
    executed: bool
    blocked_reason: str | None = None
    planned_commands: list[OscCommand] = Field(default_factory=list)
    osc_commands: list[OscCommand] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    decision: DramaturgyDecision
    force: bool = False
    stagger: bool = True


class ExecuteLayeredRequest(BaseModel):
    decision: DramaturgyDecision
    anarchy_level: float = Field(default=0.5, ge=0.0, le=1.0)
    stack: bool = True
    skip_interval_check: bool = True
    stagger: bool = False


class ExecuteResponse(BaseModel):
    executed: bool
    blocked_reason: str | None = None
    osc_commands: list[OscCommand] = Field(default_factory=list)


class DirectorStatusResponse(BaseModel):
    safety: dict[str, bool]
    active_cues: list[str]
    last_event: DialogueEvent | None = None
    last_decision: DramaturgyDecision | None = None
    last_executed: bool | None = None
    last_blocked_reason: str | None = None
    last_planned_commands: list[OscCommand] = Field(default_factory=list)
    last_osc_commands: list[OscCommand] = Field(default_factory=list)


class OscTestRequest(BaseModel):
    clip_id: str = "clyde"
    sound_cue_id: str = "maschinen_grundader"
    light_scene_id: str = "vorbuehnenzug"
    send_visual: bool = True
    send_sound: bool = True
    send_light: bool = True
    opacity: float = Field(default=0.8, ge=0.0, le=1.0)
    volume: float = Field(default=0.5, ge=0.0, le=1.0)
    fade_time: float = Field(default=4.0, ge=0.0)
    stagger: bool = True


class OscTestResponse(BaseModel):
    sent: bool
    dry_run: bool
    target: str
    executed: bool
    blocked_reason: str | None = None
    messages: list[OscCommand] = Field(default_factory=list)


class TechnikStopRequest(BaseModel):
    send_visual: bool = True
    send_sound: bool = True
    send_light: bool = True


class TechnikHoldStatusResponse(BaseModel):
    active: bool
    send_visual: bool = False
    send_sound: bool = False
    send_light: bool = False
    clip_id: str | None = None
    sound_cue_id: str | None = None
    light_scene_id: str | None = None


class LightDeskStatusResponse(BaseModel):
    tcp_connected: bool
    scene_id: str | None = None
    hold_active: bool = False


class LightSendRequest(BaseModel):
    light_scene_id: str = Field(min_length=1)


class RecordingRequest(BaseModel):
    recording_id: str = Field(min_length=1)


class RecordingStatusResponse(BaseModel):
    active: bool
    recording_id: str | None = None
