"""execute_layered must not send cues while emergency stop is active."""

from unittest.mock import MagicMock

from app.director.cues.cue_models import DramaturgyDecision, SoundAction, SoundCue
from app.director.cues.safety import SafetyState
from app.director.pipeline import DirectorPipeline


def test_execute_layered_blocked_during_emergency_stop() -> None:
    safety = SafetyState()
    safety.emergency_stop()

    sound = MagicMock()
    pipeline = DirectorPipeline(
        media_db=MagicMock(),
        safety=safety,
        sound=sound,
        touchdesigner=MagicMock(),
        pixera=MagicMock(),
        lighting=MagicMock(),
    )

    decision = DramaturgyDecision(
        sound=SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="maschinen_grundader"),
        reason="test",
        tags=[],
        mood="neutral",
        intensity=0.5,
        timestamp=0,
    )

    result = pipeline.execute_layered(decision, skip_interval_check=True)

    assert result.executed is False
    assert result.blocked_reason == "emergency_stop_active"
    assert result.osc_commands == []
    sound.execute.assert_not_called()
