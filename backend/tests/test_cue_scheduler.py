from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.director.cues.scheduler import CueScheduler
from app.director.cues.safety import SafetyState
from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.media.database import MediaDatabase
from app.director.pipeline import DirectorPipeline


def _sample_decision() -> DramaturgyDecision:
    return DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="kuh"),
        sound=SoundCue(cue_id="dummy_drone"),
        light=LightCue(scene_id="vorbuehnenzug"),
        reason="test",
        tags=["memory"],
        mood="melancholisch",
        intensity=0.6,
        timestamp=1.0,
    )


def test_scheduler_blocks_when_autopilot_disabled() -> None:
    safety = SafetyState(autopilot_enabled=False)
    scheduler = CueScheduler(MediaDatabase().rules, safety)
    allowed, reason = scheduler.can_execute(_sample_decision())
    assert allowed is False
    assert reason == "autopilot_disabled"


def test_scheduler_blocks_blackout_when_locked() -> None:
    safety = SafetyState(blackout_locked=True)
    scheduler = CueScheduler(MediaDatabase().rules, safety)
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.FADE_TO_BLACK),
        reason="blackout",
    )
    allowed, reason = scheduler.can_execute(decision)
    assert allowed is False
    assert reason == "blackout_locked"


def test_pipeline_respects_visuals_disabled() -> None:
    safety = SafetyState(visuals_enabled=False)
    pipeline = DirectorPipeline(safety=safety)
    event = DialogueEvent(
        speaker=DialogueSpeaker.AI_A,
        text="Erinnerung",
        topic="Erinnerung",
        mood="melancholisch",
        intensity=0.6,
        tags=["memory"],
        timestamp=1.0,
    )
    result = pipeline.process(event)
    assert result.executed is False
    assert result.blocked_reason == "visuals_disabled"
