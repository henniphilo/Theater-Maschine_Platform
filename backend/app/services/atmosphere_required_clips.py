"""Hard staging rule: Bonnie and Clyde must recur as atmosphere OSC clips."""

from __future__ import annotations

from collections.abc import Sequence

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    VisualAction,
    VisualCue,
    VisualOutputAssignment,
)
from app.services.teil2_projector_assignment import STAGE_BEAMER_ORDER

# OSC ohne Avatare — Begleitvideo, mehrmals über die Aufführung.
# Keep in sync with video_scope.RECURRING_ATMOSPHERE_CLIP_IDS.
REQUIRED_RECURRING_ATMOSPHERE_CLIPS: tuple[str, ...] = ("clyde", "bonnie")
MIN_RECURRING_APPEARANCES = 4
# Every 3rd atmosphere fill prefers Clyde/Bonnie (cadence that worked in rehearsal).
_RECURRING_EVERY_N = 3
_NEAR_SEC = 8.0
# Cap so long shows stay dense without turning into a Bonnie/Clyde loop.
_MAX_RECURRING_APPEARANCES = 10


def min_recurring_appearances(total_sec: float) -> int:
    """Guarantee enough Clyde/Bonnie hits over the show (was capped at 5 → felt sparse)."""
    return max(
        MIN_RECURRING_APPEARANCES,
        min(_MAX_RECURRING_APPEARANCES, round(total_sec / 30.0)),
    )


def available_recurring_clips(allowed_clips: Sequence[str] | set[str]) -> list[str]:
    allowed = set(allowed_clips)
    return [clip_id for clip_id in REQUIRED_RECURRING_ATMOSPHERE_CLIPS if clip_id in allowed]


def pick_recurring_or_pool_clip(pool: Sequence[str], clip_index: int) -> str:
    """Every 3rd atmosphere fill uses Clyde/Bonnie; pool order still prefers them first."""
    if not pool:
        return ""
    recurring = available_recurring_clips(pool)
    if recurring and clip_index % _RECURRING_EVERY_N == 0:
        return recurring[(clip_index // _RECURRING_EVERY_N) % len(recurring)]
    return pool[clip_index % len(pool)]


def _assign_atmosphere_visual(clip_id: str, projector: str) -> VisualCue:
    return VisualCue(
        clip_id=clip_id,
        video_type="atmosphere",
        projector=projector,  # type: ignore[arg-type]
        blend_mode="layer",
        lock_until_finished=False,
        can_be_interrupted=True,
        outputs=[VisualOutputAssignment(output_id=projector, clip_id=clip_id)],
    )


def _play_clip_id(point: CuePoint) -> str | None:
    visual = point.visual
    if visual is None or not visual.clip_id:
        return None
    action = visual.action
    value = action.value if isinstance(action, VisualAction) else str(action)
    if value in {VisualAction.FADE_TO_BLACK.value, VisualAction.STOP_CLIP.value}:
        return None
    return visual.clip_id


def _projector_of(point: CuePoint) -> str | None:
    visual = point.visual
    if visual is None:
        return None
    if visual.projector:
        return visual.projector
    if visual.outputs:
        return visual.outputs[0].output_id
    return None


def count_atmosphere_clip(points: Sequence[CuePoint], clip_id: str) -> int:
    return sum(1 for point in points if _play_clip_id(point) == clip_id)


def _target_times(total_sec: float, count: int, *, offset_sec: float = 0.0) -> list[float]:
    if count <= 0 or total_sec <= 0:
        return []
    start = 0.4 + offset_sec
    end = max(start + 1.0, total_sec * 0.90)
    if count == 1:
        return [round(min(end, (start + end) / 2), 2)]
    step = (end - start) / (count - 1)
    return [round(min(end, start + index * step), 2) for index in range(count)]


def _occupied_projectors(points: Sequence[CuePoint], time_sec: float) -> set[str]:
    occupied: set[str] = set()
    for point in points:
        if abs(point.time_offset_sec - time_sec) > 0.15:
            continue
        projector = _projector_of(point)
        if projector:
            occupied.add(projector)
    return occupied


def _has_clip_near(points: Sequence[CuePoint], clip_id: str, time_sec: float) -> bool:
    return any(
        _play_clip_id(point) == clip_id and abs(point.time_offset_sec - time_sec) <= _NEAR_SEC
        for point in points
    )


def _replace_nearby(
    points: list[CuePoint],
    *,
    clip_id: str,
    time_sec: float,
    required: set[str],
) -> bool:
    candidates: list[tuple[float, int]] = []
    for index, point in enumerate(points):
        current = _play_clip_id(point)
        if current is None:
            continue
        delta = abs(point.time_offset_sec - time_sec)
        if delta > _NEAR_SEC:
            continue
        if current == clip_id:
            return True
        if current in required:
            continue
        candidates.append((delta, index))
    if not candidates:
        return False
    candidates.sort()
    index = candidates[0][1]
    point = points[index]
    projector = _projector_of(point) or "adam"
    points[index] = point.model_copy(
        update={"visual": _assign_atmosphere_visual(clip_id, projector)}
    )
    return True


def _add_clip_at(
    points: list[CuePoint],
    *,
    clip_id: str,
    time_sec: float,
    windows: Sequence[object],
) -> bool:
    from app.services.teil2_atmosphere_scheduler import free_projectors_at

    occupied = _occupied_projectors(points, time_sec)
    free = [p for p in free_projectors_at(windows, time_sec) if p not in occupied]
    if not free:
        return False
    projector = next((p for p in STAGE_BEAMER_ORDER if p in free), free[0])
    points.append(
        CuePoint(
            trigger=CuePointTrigger.TIME,
            time_offset_sec=round(time_sec, 2),
            function="atmosphaere",
            intensity=0.55,
            visual=_assign_atmosphere_visual(clip_id, projector),
        )
    )
    return True


def ensure_recurring_atmosphere_clips(
    points: list[CuePoint],
    *,
    windows: Sequence[object],
    total_sec: float,
    allowed_clips: set[str],
) -> list[CuePoint]:
    """Guarantee Bonnie/Clyde appear several times as Begleitvideo OSC cues."""
    required = available_recurring_clips(allowed_clips)
    if not required:
        return points
    updated = list(points)
    min_each = min_recurring_appearances(total_sec)
    slot_span = (total_sec * 0.82) / max(1, min_each)
    for clip_index, clip_id in enumerate(required):
        offset = (slot_span / 2.0) * clip_index
        if count_atmosphere_clip(updated, clip_id) >= min_each:
            continue
        for time_sec in _target_times(total_sec, min_each, offset_sec=offset):
            if count_atmosphere_clip(updated, clip_id) >= min_each:
                break
            if _has_clip_near(updated, clip_id, time_sec):
                continue
            if _replace_nearby(
                updated,
                clip_id=clip_id,
                time_sec=time_sec,
                required=set(required),
            ):
                continue
            _add_clip_at(updated, clip_id=clip_id, time_sec=time_sec, windows=windows)
    updated.sort(key=lambda item: item.time_offset_sec)
    return updated
