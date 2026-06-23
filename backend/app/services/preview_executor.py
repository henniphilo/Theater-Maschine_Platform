import asyncio
import logging

from app.director.cues.cue_models import (
    DramaturgyDecision,
    LightCue,
    OscCommand,
    ProjectorTarget,
    SoundCue,
    VisualCue,
)
from app.director.outputs.osc_commands import build_osc_commands
from app.director.pipeline import DirectorPipeline
from app.schemas.part1_selection import (
    PREVIEW_DURATION_LIGHT_SEC,
    PREVIEW_DURATION_MUSIC_SEC,
    PREVIEW_DURATION_SOUND_SEC,
    PREVIEW_DURATION_VIDEO_SEC,
    PreviewCue,
    PreviewMedium,
)
from app.services.part1_selection_validation import _light_scene_ids, _play_sound_ids, _video_clip_ids

_logger = logging.getLogger("theatermaschine.part1.preview")

DEFAULT_VIDEO_PROJECTOR: ProjectorTarget = "rz21"


def _out_cue_id(play_id: str) -> str | None:
    if play_id.endswith("_out"):
        return play_id
    base = play_id.removesuffix("_fade_in").removesuffix("_fade_out")
    candidate = f"{base}_out"
    return candidate if candidate in _play_sound_ids() else None


def _preview_decision_for_medium(
    medium: PreviewMedium,
    medium_id: str,
    *,
    projector: ProjectorTarget | None = None,
) -> DramaturgyDecision:
    if medium in ("sound", "music"):
        return DramaturgyDecision(sound=SoundCue(cue_id=medium_id, volume=0.65))
    if medium == "video":
        target = projector or DEFAULT_VIDEO_PROJECTOR
        return DramaturgyDecision(
            visual=VisualCue(
                clip_id=medium_id,
                outputs=[{"output_id": target, "clip_id": medium_id}],
            )
        )
    return DramaturgyDecision(
        light=LightCue(scene_id=medium_id, intensity=0.5),
    )


def _stop_decision_for_medium(
    medium: PreviewMedium,
    medium_id: str,
    *,
    projector: ProjectorTarget | None = None,
) -> DramaturgyDecision | None:
    if medium in ("sound", "music"):
        out_id = _out_cue_id(medium_id)
        if out_id:
            return DramaturgyDecision(sound=SoundCue(cue_id=out_id, volume=0.0))
        return None
    if medium == "video":
        target = projector or DEFAULT_VIDEO_PROJECTOR
        return DramaturgyDecision(
            visual=VisualCue(
                clip_id="black",
                outputs=[{"output_id": target, "clip_id": "black"}],
            )
        )
    return DramaturgyDecision(light=LightCue(scene_id="blackout", replace_previous=True))


def preview_duration_sec(medium: PreviewMedium) -> float:
    if medium == "video":
        return PREVIEW_DURATION_VIDEO_SEC
    if medium == "music":
        return PREVIEW_DURATION_MUSIC_SEC
    if medium == "light":
        return PREVIEW_DURATION_LIGHT_SEC
    return PREVIEW_DURATION_SOUND_SEC


def build_preview_cue(
    medium: PreviewMedium,
    medium_id: str,
    *,
    projector: ProjectorTarget | None = None,
    duration_sec: float | None = None,
) -> PreviewCue:
    decision = _preview_decision_for_medium(medium, medium_id, projector=projector)
    # Workshop previews are UI-only — never arm the machine during dramaturgy.
    commands = build_osc_commands(decision, dry_run=True)
    return PreviewCue(
        medium=medium,
        medium_id=medium_id,
        projector=projector,
        duration_sec=duration_sec or preview_duration_sec(medium),
        osc_commands=commands,
    )


class PreviewExecutor:
    def __init__(self, pipeline: DirectorPipeline | None = None) -> None:
        self.pipeline = pipeline or DirectorPipeline()

    async def run_preview(self, preview: PreviewCue) -> list[OscCommand]:
        start_cmds = preview.osc_commands or build_preview_cue(
            preview.medium, preview.medium_id, projector=preview.projector
        ).osc_commands
        _logger.info(
            "preview_simulate_start medium=%s id=%s projector=%s duration=%.1fs",
            preview.medium,
            preview.medium_id,
            preview.projector,
            preview.duration_sec,
        )
        await asyncio.sleep(preview.duration_sec)
        stop_decision = _stop_decision_for_medium(
            preview.medium,
            preview.medium_id,
            projector=preview.projector,
        )
        stop_cmds: list[OscCommand] = []
        if stop_decision is not None:
            stop_cmds = build_osc_commands(stop_decision, dry_run=True)
        _logger.info("preview_simulate_end medium=%s id=%s", preview.medium, preview.medium_id)
        return start_cmds + stop_cmds

    async def run_sequence(self, previews: list[PreviewCue]) -> list[PreviewCue]:
        for preview in previews:
            preview.osc_commands = await self.run_preview(preview)
        return previews


def fallback_baerenklau_selection_from_catalog() -> tuple[list[str], list[str], list[str], list[str]]:
    sounds = sorted(_play_sound_ids())[:6]
    music_pool = [s for s in sorted(_play_sound_ids()) if "musik" in s or "grundader" in s]
    music = music_pool[:1] if music_pool else sounds[:1]
    videos = sorted(_video_clip_ids())[:6]
    lights = sorted(_light_scene_ids())[:6]
    return sounds, music, videos, lights
