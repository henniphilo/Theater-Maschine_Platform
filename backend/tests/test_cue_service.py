from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.cue import CueCreate, CueUpdate
from app.schemas.production import ProductionCreate
from app.services.cue_compat import domain_cue_to_planned_payload, to_visual_cue
from app.services.cue_execution_service import CueExecutionRejectedError, CueExecutionService
from app.services.cue_parameters import validate_cue_parameters
from app.services.cue_service import CueService, CueValidationError
from app.services.production_service import ProductionService


def _production(db_session, active_store) -> str:
    return ProductionService(db_session).create_production(ProductionCreate(name="Cues")).id


def test_parameter_validation_per_type() -> None:
    video = validate_cue_parameters("video", {"clip_id": "a", "opacity": 0.5})
    assert video["clip_id"] == "a"

    with pytest.raises(ValueError):
        validate_cue_parameters("osc", {"address": "no-slash"})

    wait = validate_cue_parameters("wait", {"duration_seconds": 1.25})
    assert wait["duration_seconds"] == 1.25


def test_create_rejects_bad_action(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    with pytest.raises(ValidationError):
        CueCreate(
            production_id=production_id,
            name="Bad",
            cue_type="video",
            action="set_scene",
            parameters={"clip_id": "x"},
        )


def test_crud_and_dry_run_execution(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    service = CueService(db_session)
    execution = CueExecutionService(db_session)

    cue = service.create_cue(
        CueCreate(
            production_id=production_id,
            name="Play Intro",
            cue_type="video",
            action="play_clip",
            parameters={"clip_id": "intro", "projector": "adam"},
            priority=5,
        )
    )
    assert cue.cue_type == "video"

    listed = service.list_cues(production_id=production_id, cue_type="video")
    assert len(listed) == 1

    planned = domain_cue_to_planned_payload(cue)
    assert planned["director"]["visual"]["clip_id"] == "intro"
    visual = to_visual_cue(cue)
    assert visual.projector == "adam"

    result = execution.execute(cue.id, dry_run=True)
    assert result.status == "planned"
    assert result.dry_run is True
    assert result.planned["cue_type"] == "video"

    with pytest.raises(CueExecutionRejectedError):
        execution.execute(cue.id, dry_run=False)

    service.update_cue(cue.id, CueUpdate(enabled=False))
    skipped = execution.execute(cue.id, dry_run=True)
    assert skipped.status == "skipped"


def test_light_requires_scene(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    with pytest.raises(ValidationError):
        CueCreate(
            production_id=production_id,
            name="No scene",
            cue_type="light",
            action="set_scene",
            parameters={},
        )


def test_cross_production_asset_rejected(db_session, active_store) -> None:
    from app.schemas.asset import AssetCreate
    from app.services.asset_service import AssetService

    production_id = _production(db_session, active_store)
    other_id = ProductionService(db_session).create_production(ProductionCreate(name="Other")).id
    asset = AssetService(db_session).create_asset(
        AssetCreate(
            production_id=other_id,
            name="Foreign",
            type="video",
            original_filename="a.mp4",
            storage_key="o/a.mp4",
            mime_type="video/mp4",
            size_bytes=1,
            checksum="x",
        )
    )
    with pytest.raises(CueValidationError):
        CueService(db_session).create_cue(
            CueCreate(
                production_id=production_id,
                name="Bad asset",
                cue_type="video",
                action="play_clip",
                asset_id=asset.id,
                parameters={},
            )
        )
