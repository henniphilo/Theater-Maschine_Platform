"""Pre-execution conflict checks for dramaturgy proposals."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.director.cues.cue_models import DecisionKind, DramaturgyDecision, VisualAction
from app.director.dramaturgy.state import DramaturgyState


@dataclass
class ConflictResult:
    allowed: bool
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def is_replace_or_stop(decision: DramaturgyDecision) -> bool:
    kind = decision.decision_kind
    if kind in {DecisionKind.STOP, DecisionKind.NONE, DecisionKind.MODIFY}:
        return True
    visual = decision.visual
    if visual and visual.action in {VisualAction.STOP_CLIP, VisualAction.FADE_TO_BLACK}:
        return True
    sound = decision.sound
    if sound and sound.cue_id and (sound.cue_id.endswith("_out") or "cut" in sound.cue_id.lower()):
        return True
    return False


def check_conflicts(
    decision: DramaturgyDecision,
    state: DramaturgyState,
    *,
    cooldown_seconds: float | None = None,
    asset_last_used: dict[str, float] | None = None,
) -> ConflictResult:
    warnings: list[str] = []
    kind = decision.decision_kind or DecisionKind.EXECUTE

    if kind == DecisionKind.NONE:
        return ConflictResult(allowed=True)

    if kind == DecisionKind.HOLD:
        return ConflictResult(allowed=True, warnings=["hold"])

    adding_layer = not is_replace_or_stop(decision)
    if adding_layer and state.total_media_density > 0.75:
        return ConflictResult(
            allowed=False,
            reason="media_density_too_high",
            warnings=["total_media_density exceeds 0.75"],
        )

    if state.text_density > 0.7 and adding_layer and state.total_media_density > 0.55:
        warnings.append("high_text_density_reduce_media")

    asset_id = None
    if decision.visual and decision.visual.clip_id:
        asset_id = decision.visual.clip_id
    elif decision.sound and decision.sound.cue_id:
        asset_id = decision.sound.cue_id

    if asset_id:
        repeats = state.repeated_assets.get(asset_id, 0)
        if repeats >= 3 and adding_layer:
            return ConflictResult(
                allowed=False,
                reason="asset_repeated_too_often",
                warnings=[f"{asset_id} used {repeats} times"],
            )
        if asset_last_used and cooldown_seconds and cooldown_seconds > 0:
            last = asset_last_used.get(asset_id)
            if last is not None and state.time_since_last_cue < cooldown_seconds and adding_layer:
                return ConflictResult(
                    allowed=False,
                    reason="asset_cooldown_active",
                    warnings=[f"{asset_id} cooldown {cooldown_seconds}s"],
                )

    if (
        decision.visual
        and decision.sound
        and state.video_density > 0.6
        and state.music_density > 0.6
        and adding_layer
    ):
        warnings.append("music_and_video_both_dense")

    return ConflictResult(allowed=True, warnings=warnings)
