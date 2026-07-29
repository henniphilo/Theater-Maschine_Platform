"""Map legacy German dramaturgy function strings to typed enums."""

from __future__ import annotations

from app.director.cues.cue_models import DramaturgicalFunction

_LEGACY_FUNCTION_MAP: dict[str, DramaturgicalFunction] = {
    "verstärken": DramaturgicalFunction.SUPPORT,
    "unterstützen": DramaturgicalFunction.SUPPORT,
    "widersprechen": DramaturgicalFunction.CONTRAST,
    "entlarven": DramaturgicalFunction.CONTRAST,
    "überlagern": DramaturgicalFunction.SUPPORT,
    "auslöschen": DramaturgicalFunction.RELEASE,
    "reduzieren": DramaturgicalFunction.RELEASE,
    "verzögern": DramaturgicalFunction.TRANSITION,
    "wiederkehren": DramaturgicalFunction.RECALL,
    "stören": DramaturgicalFunction.DISRUPTION,
    "entfremden": DramaturgicalFunction.DISRUPTION,
    "desorientieren": DramaturgicalFunction.DISRUPTION,
    "halten": DramaturgicalFunction.SPACE,
    "support": DramaturgicalFunction.SUPPORT,
    "contrast": DramaturgicalFunction.CONTRAST,
    "intensification": DramaturgicalFunction.INTENSIFICATION,
    "release": DramaturgicalFunction.RELEASE,
    "transition": DramaturgicalFunction.TRANSITION,
    "recall": DramaturgicalFunction.RECALL,
    "disruption": DramaturgicalFunction.DISRUPTION,
    "foreshadowing": DramaturgicalFunction.FORESHADOWING,
    "space": DramaturgicalFunction.SPACE,
}

_FUNCTION_LABELS_DE: dict[DramaturgicalFunction, str] = {
    DramaturgicalFunction.SUPPORT: "Unterstützung",
    DramaturgicalFunction.CONTRAST: "Kontrast",
    DramaturgicalFunction.INTENSIFICATION: "Intensivierung",
    DramaturgicalFunction.RELEASE: "Reduktion",
    DramaturgicalFunction.TRANSITION: "Übergang",
    DramaturgicalFunction.RECALL: "Wiederaufnahme",
    DramaturgicalFunction.DISRUPTION: "Störung",
    DramaturgicalFunction.FORESHADOWING: "Andeutung",
    DramaturgicalFunction.SPACE: "Leerstelle",
}


def normalize_dramaturgical_function(value: str | DramaturgicalFunction | None) -> DramaturgicalFunction | None:
    if value is None:
        return None
    if isinstance(value, DramaturgicalFunction):
        return value
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in _LEGACY_FUNCTION_MAP:
        return _LEGACY_FUNCTION_MAP[normalized]
    try:
        return DramaturgicalFunction(normalized)
    except ValueError:
        return None


def dramaturgical_function_label(function: DramaturgicalFunction | str | None) -> str:
    parsed = normalize_dramaturgical_function(function) if not isinstance(function, DramaturgicalFunction) else function
    if parsed is None:
        return ""
    return _FUNCTION_LABELS_DE.get(parsed, parsed.value)
