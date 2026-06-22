from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundCue, VisualCue, VisualAction
from app.director.cues.scheduler import CueScheduler
from app.director.cues.safety import SafetyState
from app.director.media.database import DramaturgyRules


def _decision() -> DramaturgyDecision:
    return DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde"),
        sound=SoundCue(cue_id="maschinen_grundader"),
        light=LightCue(scene_id="vorbuehnenzug"),
        reason="test",
    )


def test_scheduler_skip_interval_check_allows_rapid_cues() -> None:
    safety = SafetyState()
    safety.autopilot_enabled = True
    scheduler = CueScheduler(DramaturgyRules(), safety)
    decision = _decision()

    allowed, reason = scheduler.can_execute(decision)
    assert allowed
    scheduler.mark_executed(decision)

    allowed_again, block_reason = scheduler.can_execute(decision)
    assert not allowed_again
    assert block_reason == "video_cue_too_soon"

    allowed_layered, layered_reason = scheduler.can_execute(
        decision,
        anarchy_level=0.9,
        skip_interval_check=True,
    )
    assert allowed_layered
    assert layered_reason is None
