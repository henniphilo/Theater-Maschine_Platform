"""Helpers for operator-facing short dramaturgy reasons."""

from __future__ import annotations

import re

from app.director.cues.cue_models import (
    DecisionKind,
    DramaturgicalFunction,
    DramaturgyDecision,
)
from app.director.dramaturgy.function_mapping import normalize_dramaturgical_function

_BAD_REASON_PATTERNS = (
    re.compile(r"modell", re.I),
    re.compile(r"wahrscheinlich", re.I),
    re.compile(r"passt zur szene", re.I),
    re.compile(r"tag erkannt", re.I),
    re.compile(r"interessant", re.I),
)

_MOOD_REASONS: dict[str, str] = {
    "tension": "Verstärkt die zunehmende Spannung.",
    "melancholisch": "Setzt einen nachdenklichen Klangraum.",
    "neutral": "Begleitet die Passage dezent.",
    "intimate": "Schafft einen intimen Klangraum.",
    "chaos": "Erhöht die dramaturgische Unruhe.",
}


def is_valid_reason_short(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or len(cleaned) > 160:
        return False
    if cleaned.count(".") > 2:
        return False
    return not any(pattern.search(cleaned) for pattern in _BAD_REASON_PATTERNS)


def infer_dramaturgical_function(
    *,
    mood: str,
    intensity: float,
    tags: list[str],
    legacy_function: str = "",
) -> DramaturgicalFunction:
    """Infer typed function from legacy strings or heuristics."""
    mapped = normalize_dramaturgical_function(legacy_function)
    if mapped is not None:
        return mapped
    if "silence" in tags or "pause" in tags:
        return DramaturgicalFunction.SPACE
    if intensity >= 0.75:
        return DramaturgicalFunction.INTENSIFICATION
    if mood in {"tension", "chaos"}:
        return DramaturgicalFunction.INTENSIFICATION
    if mood in {"melancholisch", "intimate"}:
        return DramaturgicalFunction.SUPPORT
    return DramaturgicalFunction.SUPPORT


def synthesize_reason_short(
    *,
    mood: str,
    intensity: float,
    tags: list[str],
    has_video: bool,
    has_sound: bool,
    has_light: bool,
    dramaturgical_function: DramaturgicalFunction | None = None,
) -> str:
    if dramaturgical_function == DramaturgicalFunction.SPACE:
        return "Lässt die Passage bewusst ohne mediale Begleitung beginnen."
    if dramaturgical_function == DramaturgicalFunction.RELEASE:
        return "Reduziert die Medien-Dichte vor dem nächsten Moment."
    if dramaturgical_function == DramaturgicalFunction.CONTRAST:
        return "Setzt einen bewussten Kontrapunkt zum gesprochenen Text."
    if dramaturgical_function == DramaturgicalFunction.RECALL:
        return "Nimmt ein früheres Motiv wieder auf."
    if mood in _MOOD_REASONS:
        return _MOOD_REASONS[mood]
    if has_video and has_sound:
        return "Verdichtet Bild und Klang zur aktuellen Textstelle."
    if has_video:
        return "Eröffnet eine visuelle Ebene zur Textstelle."
    if has_sound:
        return "Eröffnet eine klangliche Ebene zur Textstelle."
    if has_light:
        return "Setzt die Lichtstimmung zur Textstelle."
    if tags:
        return f"Reagiert auf {', '.join(tags[:2])} in der Passage."
    if intensity >= 0.7:
        return "Verstärkt die zunehmende Intensität."
    return "Begleitet die Passage dramaturgisch."


def enrich_decision_metadata(decision: DramaturgyDecision) -> DramaturgyDecision:
    """Fill reason_short and dramaturgical_function when missing (backward compatible)."""
    has_video = decision.visual is not None
    has_sound = decision.sound is not None
    has_light = decision.light is not None
    legacy_function = ""
    if decision.cue_points and decision.cue_points[0].function:
        legacy_function = decision.cue_points[0].function

    function = decision.dramaturgical_function
    if function is None:
        function = infer_dramaturgical_function(
            mood=decision.mood,
            intensity=decision.intensity,
            tags=list(decision.tags),
            legacy_function=legacy_function,
        )
        decision.dramaturgical_function = function

    if decision.decision_kind is None:
        if not has_video and not has_sound and not has_light:
            if decision.cue_points and all(
                p.visual is None and p.sound is None and p.light is None for p in decision.cue_points
            ):
                decision.decision_kind = DecisionKind.NONE
            else:
                decision.decision_kind = DecisionKind.EXECUTE
        else:
            decision.decision_kind = DecisionKind.EXECUTE

    if not decision.reason_short:
        if decision.reason and is_valid_reason_short(decision.reason):
            decision.reason_short = decision.reason.strip()
        else:
            decision.reason_short = synthesize_reason_short(
                mood=decision.mood,
                intensity=decision.intensity,
                tags=list(decision.tags),
                has_video=has_video,
                has_sound=has_sound,
                has_light=has_light,
                dramaturgical_function=function,
            )
    return decision


def display_reason(decision: DramaturgyDecision) -> str:
    if decision.reason_short:
        return decision.reason_short
    return decision.reason
