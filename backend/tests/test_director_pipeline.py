from unittest.mock import MagicMock, patch

from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.pipeline import DirectorPipeline


def _memory_event() -> DialogueEvent:
    return DialogueEvent(
        speaker=DialogueSpeaker.AI_A,
        text="Erinnerung ist vielleicht nur eine technische Störung.",
        topic="Erinnerung",
        mood="melancholisch",
        intensity=0.72,
        tags=["memory", "erinnerung"],
        timestamp=1.0,
    )


def test_plan_does_not_send_osc() -> None:
    pipeline = DirectorPipeline()
    with patch("app.director.outputs.osc_commands.send_osc_commands") as send_mock:
        result = pipeline.plan(_memory_event())

    send_mock.assert_not_called()
    assert result.executed is False
    assert result.planned_commands
    assert result.osc_commands == []


def test_execute_sends_osc_commands() -> None:
    pipeline = DirectorPipeline()
    planned = pipeline.plan(_memory_event())
    with patch("app.director.pipeline.send_osc_batch", wraps=__import__(
        "app.director.outputs.osc_queue", fromlist=["send_osc_batch"]
    ).send_osc_batch) as send_mock:
        result = pipeline.execute(planned.decision, stagger=False)

    assert send_mock.call_count >= 1
    assert result.executed is True
    assert result.osc_commands
    assert pipeline.state.last_osc_commands == result.osc_commands


def test_process_sequenced_mode_plans_only(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "director_execute_mode", "sequenced")
    pipeline = DirectorPipeline()
    with patch("app.director.outputs.osc_commands.send_osc_commands") as send_mock:
        result = pipeline.process(_memory_event())

    send_mock.assert_not_called()
    assert result.executed is False
    assert result.planned_commands


def test_process_immediate_mode_executes(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "director_execute_mode", "immediate")
    monkeypatch.setattr(settings, "visual_output", "touchdesigner")
    pipeline = DirectorPipeline()
    touchdesigner = MagicMock()
    pipeline.touchdesigner = touchdesigner
    result = pipeline.process(_memory_event())

    assert result.executed is True
    assert result.osc_commands
    touchdesigner.play_clip.assert_called()
