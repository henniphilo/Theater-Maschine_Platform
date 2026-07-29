from app.director.cues.cue_models import (
    DecisionKind,
    DramaturgicalFunction,
    DramaturgyDecision,
    SoundAction,
    SoundCue,
    VisualAction,
    VisualCue,
)
from app.director.dramaturgy.conflict_check import check_conflicts, is_replace_or_stop
from app.director.dramaturgy.reason_short import enrich_decision_metadata, is_valid_reason_short
from app.director.dramaturgy.state import DramaturgyState


def test_enrich_decision_adds_reason_short() -> None:
    decision = DramaturgyDecision(mood="tension", intensity=0.8, tags=["memory"])
    enriched = enrich_decision_metadata(decision)
    assert enriched.reason_short
    assert enriched.dramaturgical_function == DramaturgicalFunction.INTENSIFICATION


def test_none_decision_space_function() -> None:
    decision = DramaturgyDecision(
        decision_kind=DecisionKind.NONE,
        dramaturgical_function=DramaturgicalFunction.SPACE,
        reason_short="Lässt die Passage bewusst ohne Begleitung beginnen.",
        mood="neutral",
        intensity=0.3,
    )
    enriched = enrich_decision_metadata(decision)
    assert enriched.decision_kind == DecisionKind.NONE
    assert "Begleitung" in enriched.reason_short


def test_invalid_reason_short_rejected() -> None:
    assert not is_valid_reason_short("Sound passt zur Szene.")
    assert is_valid_reason_short("Verstärkt die zunehmende Bedrohung.")


def test_conflict_blocks_high_density_layer() -> None:
    state = DramaturgyState(total_media_density=0.9, music_density=0.8, video_density=0.7)
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
        mood="tension",
        intensity=0.8,
    )
    result = check_conflicts(decision, state)
    assert not result.allowed
    assert result.reason == "media_density_too_high"


def test_stop_actions_allowed_at_high_density() -> None:
    state = DramaturgyState(total_media_density=0.9)
    decision = DramaturgyDecision(
        sound=SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="alle_sounds_cut"),
        decision_kind=DecisionKind.STOP,
    )
    assert is_replace_or_stop(decision)
    result = check_conflicts(decision, state)
    assert result.allowed
