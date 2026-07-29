from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision
from app.director.dramaturgy.function_mapping import normalize_dramaturgical_function


def map_legacy_function(function: str) -> str:
    """Return canonical enum value string for a legacy German function label."""
    parsed = normalize_dramaturgical_function(function)
    return parsed.value if parsed else function


def cue_point_is_active(point: CuePoint) -> bool:
    return point.visual is not None or point.sound is not None or point.light is not None


def normalize_cue_points(decision: DramaturgyDecision) -> list[CuePoint]:
    if decision.cue_points:
        return list(decision.cue_points)

    if decision.visual or decision.sound or decision.light:
        return [
            CuePoint(
                trigger=CuePointTrigger.START,
                time_offset_sec=0.0,
                function="verstärken",
                intensity=decision.intensity,
                visual=decision.visual,
                sound=decision.sound,
                light=decision.light,
            )
        ]
    return []


def decision_from_cue_point(base: DramaturgyDecision, point: CuePoint) -> DramaturgyDecision:
    reason = base.reason_short or base.reason
    if point.function:
        reason = f"[{point.function}] {reason}".strip()

    function = base.dramaturgical_function
    if function is None and point.function:
        function = normalize_dramaturgical_function(point.function)

    return DramaturgyDecision(
        visual=point.visual,
        sound=point.sound,
        light=point.light,
        reason=reason,
        reason_short=base.reason_short,
        tags=list(base.tags),
        mood=base.mood,
        intensity=point.intensity,
        timestamp=base.timestamp,
        dramaturgical_reading=base.dramaturgical_reading,
        dramaturgical_function=function,
        decision_kind=base.decision_kind,
        confidence=base.confidence,
        cue_points=[],
    )


def min_cue_points_for_text(text: str) -> int:
    length = len(text.strip())
    if length < 200:
        return 1
    if length < 500:
        return 2
    if length < 1000:
        return 3
    if length < 2000:
        return 4
    return min(6, 5 + length // 2000)
