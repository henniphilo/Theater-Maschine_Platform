"""Dramaturgy must not occupy avatar beamers."""

from __future__ import annotations

from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.inszenierung import AnarchyCurve, CompositionMoment
from app.services.teil2_beat_dramaturgy import build_dramaturgy_for_beat
from app.services.teil2_script_service import build_timeline_from_csv


def test_dramaturgy_visual_avoids_avatar_projector() -> None:
    plan = build_timeline_from_csv(anarchy_curve=AnarchyCurve(start=0.2, end=0.2))
    moment = plan.moments[0]
    dramaturgy = build_dramaturgy_for_beat(moment)

    avatar_projector = moment.avatar_layers[0].projector
    assert avatar_projector == "rz21"

    cmds = build_osc_commands(dramaturgy, dry_run=True, video_scope="part2")
    pixera_targets = [cmd.args[0].split(".")[0] for cmd in cmds if cmd.bridge == "pixera"]
    assert pixera_targets
    assert all("RZ21" not in target.upper() for target in pixera_targets)

    for point in dramaturgy.cue_points:
        if point.visual and point.visual.projector:
            assert point.visual.projector != avatar_projector


def test_avatar_visual_cue_still_on_reserved_projector() -> None:
    plan = build_timeline_from_csv(anarchy_curve=AnarchyCurve(start=0.2, end=0.2))
    moment = plan.moments[0]
    visual = moment.avatar_layers[0].visual_cue
    assert visual is not None
    assert visual.projector == "rz21"
    assert visual.video_type == "avatar"
