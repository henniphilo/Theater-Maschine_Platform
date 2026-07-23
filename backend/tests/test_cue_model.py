from __future__ import annotations

from datetime import datetime

from app.models.cue import Cue, CueType
from app.models.production import Production


def _seed_production(db_session) -> Production:
    row = Production(name="Cue Show", slug="cue-show")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_cue_model_defaults(db_session) -> None:
    production = _seed_production(db_session)
    row = Cue(
        production_id=production.id,
        name="Intro Video",
        cue_type=CueType.VIDEO.value,
        action="play_clip",
        parameters={"clip_id": "intro"},
        enabled=True,
        priority=10,
        cooldown_seconds=1.5,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id
    assert len(row.id) == 36
    assert row.production_id == production.id
    assert row.cue_type == "video"
    assert row.parameters == {"clip_id": "intro"}
    assert row.enabled is True
    assert row.priority == 10
    assert isinstance(row.created_at, datetime)
