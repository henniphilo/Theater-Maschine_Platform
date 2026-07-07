"""Runtime routing of dramaturgy away from active avatar beamers."""

from datetime import UTC, datetime, timedelta

from app.director.cues.cue_models import DramaturgyDecision, VisualCue
from app.director.cues.projector_state import ProjectorState
from app.services.teil2_dramaturgy_routing import (
    active_avatar_reserved_projectors,
    route_dramaturgy_away_from_projectors,
)


def test_active_avatar_reserved_projectors() -> None:
    projectors = ProjectorState()
    now = datetime.now(UTC)
    cue = VisualCue(
        action="play_clip",
        clip_id="bak1_nicolaspflanzen3",
        video_type="avatar",
        projector="rz21",
        lock_until_finished=True,
        duration_ms=5000,
    )
    projectors.lock_after_play(cue, now=now, text_excerpt="test")
    reserved = active_avatar_reserved_projectors(projectors, now=now)
    assert "rz21" in reserved
    assert "adam" not in reserved


def test_route_dramaturgy_visual_to_free_beamer() -> None:
    decision = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.5,
        visual=VisualCue(
            action="play_clip",
            clip_id="affenslowodysee2001",
            video_type="atmosphere",
        ),
    )
    routed = route_dramaturgy_away_from_projectors(decision, {"rz21", "adam"}, seed=1)
    assert routed.visual is not None
    assert routed.visual.projector not in {"rz21", "adam"}
