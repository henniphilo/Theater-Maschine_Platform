import pytest

from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.dramaturgy.llm_director import DramaturgyValidationError, LLMDirector


def _event() -> DialogueEvent:
    return DialogueEvent(
        speaker=DialogueSpeaker.AI_A,
        text="Erinnerung ist eine Störung.",
        topic="Erinnerung",
        mood="melancholisch",
        intensity=0.6,
        tags=["memory"],
        timestamp=1.0,
    )


def test_validator_rejects_unknown_clip() -> None:
    director = LLMDirector()
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="does_not_exist"),
        sound=SoundCue(cue_id="dummy_drone"),
        light=LightCue(scene_id="vorbuehnenzug"),
        reason="test",
    )
    with pytest.raises(DramaturgyValidationError):
        director.validate_decision(decision)


def test_rules_mode_decide(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "director_dramaturgy_mode", "rules")
    director = LLMDirector()

    import asyncio

    decision = asyncio.run(director.decide(_event()))
    assert decision.visual is not None
    from app.director.media.database import MediaDatabase

    video_ids = {v.id for v in MediaDatabase().videos}
    assert decision.visual.clip_id in video_ids
