import pytest

from app.director.cues.cue_models import (
    DecisionKind,
    DramaturgicalFunction,
    DramaturgyDecision,
    LightCue,
    SoundCue,
    VisualCue,
    VisualAction,
)
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
        sound=SoundCue(cue_id="maschinen_grundader"),
        light=LightCue(scene_id="blendung_zuschauerraum"),
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
    assert decision.reason_short
    assert decision.dramaturgical_function is not None
    from app.director.media.database import MediaDatabase

    video_ids = {v.id for v in MediaDatabase().videos}
    assert decision.visual.clip_id in video_ids


def test_validator_accepts_none_decision() -> None:
    director = LLMDirector()
    decision = DramaturgyDecision(
        decision_kind=DecisionKind.NONE,
        dramaturgical_function=DramaturgicalFunction.SPACE,
        reason_short="Lässt den neuen Gedanken ohne mediale Begleitung beginnen.",
        mood="neutral",
        intensity=0.4,
        cue_points=[],
    )
    director.validate_decision(decision)


def test_validator_rejects_bad_reason_short() -> None:
    director = LLMDirector()
    decision = DramaturgyDecision(
        decision_kind=DecisionKind.NONE,
        reason_short="Sound passt zur Szene.",
        mood="neutral",
        intensity=0.4,
        cue_points=[],
    )
    with pytest.raises(DramaturgyValidationError):
        director.validate_decision(decision)


def test_rules_mode_prefers_silence_when_dense(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    from app.director.dramaturgy.state import DramaturgyState

    monkeypatch.setattr(settings, "director_dramaturgy_mode", "rules")
    director = LLMDirector()
    state = DramaturgyState(total_media_density=0.8, music_density=0.7, video_density=0.7)
    event = DialogueEvent(
        speaker=DialogueSpeaker.AI_A,
        text="Ruhe.",
        topic="Pause",
        mood="neutral",
        intensity=0.3,
        tags=["ruhe"],
        timestamp=2.0,
    )
    import asyncio

    decision = asyncio.run(director.decide(event, dramaturgy_state=state))
    assert decision.decision_kind == DecisionKind.NONE
    assert decision.dramaturgical_function == DramaturgicalFunction.SPACE


def test_call_llm_includes_dramaturgy_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "director_dramaturgy_mode", "llm")
    director = LLMDirector()
    captured: dict[str, object] = {}

    async def fake_generate(provider, model, messages, max_tokens=0):
        captured["user"] = messages[1]["content"]
        return (
            '{"decision_kind":"none","dramaturgical_function":"space",'
            '"reason_short":"Lässt den neuen Gedanken ohne mediale Begleitung beginnen.",'
            '"confidence":0.9,"cue_points":[],"reason":"test","mood":"neutral",'
            '"intensity":0.4,"timestamp":1}'
        )

    monkeypatch.setattr(director.ai, "generate", fake_generate)
    import asyncio

    decision = asyncio.run(
        director.decide(
            _event(),
            dramaturgy_state={"total_media_density": 0.91, "active_video_layers": 2},
        )
    )
    assert "Live-DramaturgyState" in str(captured.get("user", ""))
    assert "0.91" in str(captured.get("user", ""))
    assert decision.decision_kind == DecisionKind.NONE
