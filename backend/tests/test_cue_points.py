from app.director.cues.cue_models import DramaturgicalFunction
from app.director.cues.cue_points import map_legacy_function
from app.director.dramaturgy.function_mapping import normalize_dramaturgical_function


def test_map_legacy_german_functions() -> None:
    assert map_legacy_function("verstärken") == "support"
    assert map_legacy_function("widersprechen") == "contrast"
    assert map_legacy_function("auslöschen") == "release"
    assert map_legacy_function("wiederkehren") == "recall"


def test_normalize_enum_values() -> None:
    assert normalize_dramaturgical_function("space") == DramaturgicalFunction.SPACE
    assert normalize_dramaturgical_function("contrast") == DramaturgicalFunction.CONTRAST
