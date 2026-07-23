"""Compatibility layer between domain Cue and legacy director cue shapes.

Does not delete or replace VisualCue / SoundCue / LightCue / JSON catalogs.
"""

from __future__ import annotations

import logging
from typing import Any

from app.director.cues.cue_models import (
    LightAction,
    LightCue,
    SoundAction,
    SoundCue,
    VisualAction,
    VisualCue,
)
from app.models.cue import Cue, CueType
from app.schemas.cue import LegacyCueSummary

logger = logging.getLogger(__name__)


def domain_cue_to_planned_payload(cue: Cue) -> dict[str, Any]:
    """Map a domain Cue to an adapter-oriented planned payload (no I/O)."""
    params = dict(cue.parameters or {})
    base = {
        "cue_id": cue.id,
        "production_id": cue.production_id,
        "name": cue.name,
        "cue_type": cue.cue_type,
        "action": cue.action,
        "asset_id": cue.asset_id,
        "device_id": cue.device_id,
        "priority": cue.priority,
        "cooldown_seconds": cue.cooldown_seconds,
        "parameters": params,
    }

    if cue.cue_type == CueType.VIDEO.value:
        visual = to_visual_cue(cue)
        base["director"] = {"visual": visual.model_dump(mode="json")}
    elif cue.cue_type == CueType.AUDIO.value:
        sound = to_sound_cue(cue)
        base["director"] = {"sound": sound.model_dump(mode="json")}
    elif cue.cue_type == CueType.LIGHT.value:
        light = to_light_cue(cue)
        base["director"] = {"light": light.model_dump(mode="json")}
    elif cue.cue_type == CueType.OSC.value:
        base["director"] = {
            "osc": {
                "address": params.get("address"),
                "args": params.get("args") or [],
                "device_id": cue.device_id,
            }
        }
    elif cue.cue_type == CueType.MIDI.value:
        base["director"] = {
            "midi": {
                "note": params.get("note"),
                "channel": params.get("channel", 1),
                "velocity": params.get("velocity", 100),
                "action": cue.action,
                "catalog_cue_id": params.get("catalog_cue_id"),
                "device_id": cue.device_id,
            }
        }
    elif cue.cue_type == CueType.TEXT.value:
        base["director"] = {
            "text": {
                "action": cue.action,
                "content": params.get("content"),
                "asset_id": cue.asset_id,
            }
        }
    elif cue.cue_type == CueType.WAIT.value:
        base["director"] = {"wait": {"duration_seconds": params.get("duration_seconds")}}

    return base


def to_visual_cue(cue: Cue) -> VisualCue:
    params = cue.parameters or {}
    action = cue.action
    try:
        visual_action = VisualAction(action)
    except ValueError:
        visual_action = VisualAction.PLAY_CLIP

    projector = params.get("projector")
    if projector not in (None, "adam", "eva", "rz21", "led"):
        projector = None

    video_type = params.get("video_type") or "atmosphere"
    if video_type not in ("avatar", "atmosphere", "regie"):
        video_type = "atmosphere"

    return VisualCue(
        action=visual_action,
        clip_id=params.get("clip_id"),
        projector=projector,
        video_type=video_type,
        fade_time=float(params.get("fade_time") or 4.0),
        opacity=float(params.get("opacity") if params.get("opacity") is not None else 0.8),
        duration_ms=params.get("duration_ms"),
        blend=params.get("blend") or "slow_fade",
    )


def to_sound_cue(cue: Cue) -> SoundCue:
    params = cue.parameters or {}
    action = cue.action
    try:
        sound_action = SoundAction(action)
    except ValueError:
        sound_action = SoundAction.TRIGGER_CUE
    return SoundCue(
        action=sound_action,
        cue_id=params.get("catalog_cue_id"),
        volume=float(params.get("volume") if params.get("volume") is not None else 0.6),
    )


def to_light_cue(cue: Cue) -> LightCue:
    params = cue.parameters or {}
    action = cue.action
    try:
        light_action = LightAction(action)
    except ValueError:
        light_action = LightAction.SET_SCENE
    return LightCue(
        action=light_action,
        scene_id=params.get("scene_id"),
        scene_ids=list(params.get("scene_ids") or []),
        fade_time=float(params.get("fade_time") or 4.0),
        intensity=params.get("intensity"),
        replace_previous=bool(params.get("replace_previous", True)),
    )


def list_legacy_catalog_summaries() -> list[LegacyCueSummary]:
    """Read existing video/sound JSON catalogs without mutating them."""
    summaries: list[LegacyCueSummary] = []
    try:
        from app.services.video_cue_catalog import VideoCueCatalogService

        catalog = VideoCueCatalogService().load()
        for clip in catalog.clips:
            summaries.append(
                LegacyCueSummary(
                    source="video_cues",
                    catalog_id=clip.id,
                    label=clip.label or clip.pixera_name or clip.id,
                    cue_type="video",
                    suggested_action="play_clip",
                    details={
                        "pixera_name": clip.pixera_name,
                        "video_type": clip.video_type,
                        "projector_preference": clip.projector_preference,
                        "tags": clip.tags,
                    },
                )
            )
    except Exception:
        logger.exception("failed to load legacy video_cues catalog")

    try:
        from app.services.sound_cue_catalog import SoundCueCatalogService

        catalog = SoundCueCatalogService().load()
        for entry in catalog.cues:
            summaries.append(
                LegacyCueSummary(
                    source="sound_cues",
                    catalog_id=entry.id,
                    label=entry.label or entry.soundname or entry.id,
                    cue_type="audio",
                    suggested_action="trigger_cue",
                    details={
                        "midi_note": entry.midi_note,
                        "channel": entry.channel,
                        "action": entry.action,
                        "tags": entry.tags,
                    },
                )
            )
    except Exception:
        logger.exception("failed to load legacy sound_cues catalog")

    return summaries
