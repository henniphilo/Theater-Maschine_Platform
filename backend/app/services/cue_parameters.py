"""Typed parameter validation per domain cue_type."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.models.cue import CueType

CueTypeLiteral = Literal["video", "audio", "light", "osc", "midi", "text", "wait"]

ACTIONS_BY_TYPE: dict[str, frozenset[str]] = {
    CueType.VIDEO.value: frozenset({"play_clip", "stop_clip", "fade_to_black"}),
    CueType.AUDIO.value: frozenset({"trigger_cue", "stop_cue", "set_volume"}),
    CueType.LIGHT.value: frozenset({"set_scene", "fade_blackout", "pulse"}),
    CueType.OSC.value: frozenset({"send"}),
    CueType.MIDI.value: frozenset({"note_on", "note_off", "trigger_cue"}),
    CueType.TEXT.value: frozenset({"show", "clear"}),
    CueType.WAIT.value: frozenset({"wait"}),
}


class VideoCueParameters(BaseModel):
    clip_id: str | None = Field(default=None, max_length=80)
    projector: str | None = Field(default=None, max_length=40)
    video_type: Literal["avatar", "atmosphere", "regie"] = "atmosphere"
    fade_time: float = Field(default=4.0, ge=0.0)
    opacity: float = Field(default=0.8, ge=0.0, le=1.0)
    duration_ms: int | None = Field(default=None, ge=0)
    blend: str = Field(default="slow_fade", max_length=40)

    @field_validator("clip_id", "projector", "blend")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AudioCueParameters(BaseModel):
    catalog_cue_id: str | None = Field(default=None, max_length=80)
    volume: float = Field(default=0.6, ge=0.0, le=1.0)
    midi_note: int | None = Field(default=None, ge=0, le=127)
    channel: int | None = Field(default=None, ge=1, le=16)
    velocity: int | None = Field(default=None, ge=1, le=127)

    @field_validator("catalog_cue_id")
    @classmethod
    def strip_catalog_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LightCueParameters(BaseModel):
    scene_id: str | None = Field(default=None, max_length=80)
    scene_ids: list[str] = Field(default_factory=list)
    fade_time: float = Field(default=4.0, ge=0.0)
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    replace_previous: bool = True

    @field_validator("scene_id")
    @classmethod
    def strip_scene(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OscCueParameters(BaseModel):
    address: str = Field(..., min_length=1, max_length=200)
    args: list[Any] = Field(default_factory=list)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("/"):
            raise ValueError("OSC address must start with '/'")
        return cleaned


class MidiCueParameters(BaseModel):
    note: int | None = Field(default=None, ge=0, le=127)
    channel: int = Field(default=1, ge=1, le=16)
    velocity: int = Field(default=100, ge=0, le=127)
    catalog_cue_id: str | None = Field(default=None, max_length=80)


class TextCueParameters(BaseModel):
    content: str | None = Field(default=None, max_length=20000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class WaitCueParameters(BaseModel):
    duration_seconds: float = Field(..., gt=0.0, le=3600.0)


_PARAM_MODELS: dict[str, type[BaseModel]] = {
    CueType.VIDEO.value: VideoCueParameters,
    CueType.AUDIO.value: AudioCueParameters,
    CueType.LIGHT.value: LightCueParameters,
    CueType.OSC.value: OscCueParameters,
    CueType.MIDI.value: MidiCueParameters,
    CueType.TEXT.value: TextCueParameters,
    CueType.WAIT.value: WaitCueParameters,
}


def validate_cue_action(cue_type: str, action: str) -> str:
    cleaned = action.strip()
    allowed = ACTIONS_BY_TYPE.get(cue_type)
    if allowed is None:
        raise ValueError(f"invalid cue_type: {cue_type}")
    if cleaned not in allowed:
        raise ValueError(
            f"action '{cleaned}' is not allowed for cue_type '{cue_type}' "
            f"(allowed: {sorted(allowed)})"
        )
    return cleaned


def validate_cue_parameters(cue_type: str, parameters: dict[str, Any] | None) -> dict[str, Any]:
    model_cls = _PARAM_MODELS.get(cue_type)
    if model_cls is None:
        raise ValueError(f"invalid cue_type: {cue_type}")
    raw = parameters if parameters is not None else {}
    if not isinstance(raw, dict):
        raise ValueError("parameters must be an object")
    try:
        return model_cls.model_validate(raw).model_dump(mode="json")
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def validate_cue_type_requirements(
    *,
    cue_type: str,
    action: str,
    parameters: dict[str, Any],
    asset_id: str | None,
) -> None:
    """Cross-field rules after action/parameters are validated."""
    if cue_type == CueType.VIDEO.value and action == "play_clip":
        if not parameters.get("clip_id") and not asset_id:
            raise ValueError("video play_clip requires clip_id in parameters or asset_id")
    if cue_type == CueType.AUDIO.value and action == "trigger_cue":
        if not parameters.get("catalog_cue_id") and not asset_id and parameters.get("midi_note") is None:
            raise ValueError(
                "audio trigger_cue requires catalog_cue_id, midi_note, or asset_id"
            )
    if cue_type == CueType.LIGHT.value and action == "set_scene":
        if not parameters.get("scene_id") and not parameters.get("scene_ids"):
            raise ValueError("light set_scene requires scene_id or scene_ids")
    if cue_type == CueType.TEXT.value and action == "show":
        if not parameters.get("content") and not asset_id:
            raise ValueError("text show requires content or asset_id")
    if cue_type == CueType.MIDI.value and action in {"note_on", "note_off"}:
        if parameters.get("note") is None:
            raise ValueError(f"midi {action} requires note")
    if cue_type == CueType.MIDI.value and action == "trigger_cue":
        if parameters.get("catalog_cue_id") is None and parameters.get("note") is None:
            raise ValueError("midi trigger_cue requires note or catalog_cue_id")
