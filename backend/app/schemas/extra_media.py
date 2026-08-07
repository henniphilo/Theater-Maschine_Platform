"""Operator overlays for extra media cues and per-cue LLM/OSC flags."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


CueKind = Literal["video", "sound", "light"]
CueSource = Literal["catalog", "extra"]


class CueOverrideFlags(BaseModel):
    dramaturgy_active: bool | None = None
    removed: bool | None = None


class ExtraVideoCue(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    pixera_name: str = Field(min_length=1, max_length=80)
    label: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    """Empty list or ['*'] → all projectors; otherwise selected output ids."""
    projectors: list[str] = Field(default_factory=lambda: ["*"])
    dramaturgy_active: bool = True
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("projectors")
    @classmethod
    def normalize_projectors(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            token = item.strip().lower()
            if not token:
                continue
            if token in {"*", "all", "alle"}:
                return ["*"]
            cleaned.append(token)
        return cleaned or ["*"]


class ExtraSoundCue(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(default="", max_length=120)
    soundname: str = Field(default="", max_length=120)
    action: Literal["play", "fade_in", "fade_out", "out", "cut_all"] = "play"
    description: str = Field(default="", max_length=500)
    midi_note: int = Field(ge=0, le=127)
    channel: int | None = Field(default=None, ge=1, le=16)
    velocity: int | None = Field(default=None, ge=1, le=127)
    dramaturgy_active: bool = True
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()


class ExtraLightCue(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=120)
    channels: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    fixtures: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    intensity_min: float = Field(default=0.0, ge=0.0, le=1.0)
    intensity_max: float = Field(default=1.0, ge=0.0, le=1.0)
    fade_time: float = Field(default=4.0, ge=0.0)
    dramaturgy_active: bool = True

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()


class VideoKindOverlay(BaseModel):
    extra: list[ExtraVideoCue] = Field(default_factory=list)
    overrides: dict[str, CueOverrideFlags] = Field(default_factory=dict)


class SoundKindOverlay(BaseModel):
    extra: list[ExtraSoundCue] = Field(default_factory=list)
    overrides: dict[str, CueOverrideFlags] = Field(default_factory=dict)


class LightKindOverlay(BaseModel):
    extra: list[ExtraLightCue] = Field(default_factory=list)
    overrides: dict[str, CueOverrideFlags] = Field(default_factory=dict)


class ExtraMediaOverrides(BaseModel):
    version: int = 1
    videos: VideoKindOverlay = Field(default_factory=VideoKindOverlay)
    sounds: SoundKindOverlay = Field(default_factory=SoundKindOverlay)
    lights: LightKindOverlay = Field(default_factory=LightKindOverlay)


class ExtraVideoCreateRequest(BaseModel):
    pixera_name: str = Field(min_length=1, max_length=80)
    label: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    projectors: list[str] = Field(default_factory=lambda: ["*"])
    id: str | None = Field(default=None, max_length=80)
    dramaturgy_active: bool = True


class ExtraSoundCreateRequest(BaseModel):
    soundname: str = Field(min_length=1, max_length=120)
    midi_note: int = Field(ge=0, le=127)
    label: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    action: Literal["play", "fade_in", "fade_out", "out", "cut_all"] = "play"
    id: str | None = Field(default=None, max_length=80)
    channel: int | None = Field(default=None, ge=1, le=16)
    dramaturgy_active: bool = True


class ExtraLightCreateRequest(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=500)
    channels: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=120)
    dramaturgy_active: bool = True


class CueAdminPatchRequest(BaseModel):
    dramaturgy_active: bool | None = None
    removed: bool | None = None


class CueAdminVideoRow(BaseModel):
    id: str
    pixera_name: str
    label: str = ""
    source: CueSource
    dramaturgy_active: bool
    removed: bool
    projectors: list[str] = Field(default_factory=list)
    video_type: str = "atmosphere"


class CueAdminSoundRow(BaseModel):
    id: str
    label: str = ""
    soundname: str = ""
    action: str = "play"
    midi_note: int | None = None
    ableton_hint: str = ""
    source: CueSource
    dramaturgy_active: bool
    removed: bool


class CueAdminLightRow(BaseModel):
    id: str
    description: str = ""
    channels: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    source: CueSource
    dramaturgy_active: bool
    removed: bool


class CueAdminResponse(BaseModel):
    videos: list[CueAdminVideoRow]
    sounds: list[CueAdminSoundRow]
    lights: list[CueAdminLightRow]
    projectors: list[dict]
