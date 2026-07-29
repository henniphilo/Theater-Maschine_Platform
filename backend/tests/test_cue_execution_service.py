from __future__ import annotations

import pytest

from app.director.cues.safety import get_safety_state
from app.schemas.cue import CueCreate
from app.schemas.device import DeviceCreate
from app.schemas.production import ProductionCreate
from app.services.cue_execution_service import (
    CueExecutionRejectedError,
    CueExecutionService,
)
from app.services.cue_service import CueService
from app.services.device_service import DeviceService
from app.services.production_service import ProductionService


@pytest.fixture()
def production(db_session, active_store):
    return ProductionService(db_session).create_production(ProductionCreate(name="Exec Show"))


def test_dry_run_does_not_require_device(db_session, production) -> None:
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=production.id,
            name="Vid",
            cue_type="video",
            action="play_clip",
            parameters={"clip_id": "x"},
        )
    )
    result = CueExecutionService(db_session).execute_cue(cue, dry_run=True)
    assert result.status == "planned"
    assert result.dry_run is True


def test_disabled_cue_skipped(db_session, production) -> None:
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=production.id,
            name="Off",
            cue_type="wait",
            action="wait",
            parameters={"duration_seconds": 1},
            enabled=False,
        )
    )
    result = CueExecutionService(db_session).execute_cue(cue, dry_run=False)
    assert result.status == "skipped"


def test_emergency_rejects_real(db_session, production) -> None:
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=production.id,
            name="W",
            cue_type="wait",
            action="wait",
            parameters={"duration_seconds": 1},
        )
    )
    safety = get_safety_state()
    safety.emergency_stop()
    try:
        with pytest.raises(CueExecutionRejectedError, match="emergency"):
            CueExecutionService(db_session).execute_cue(cue, dry_run=False)
    finally:
        safety.clear_emergency_stop()


def test_real_via_dry_run_adapter(db_session, production) -> None:
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            production_id=production.id,
            name="Out",
            adapter_type="dry_run",
            enabled=True,
            configuration={},
        )
    )
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=production.id,
            name="OSC",
            cue_type="osc",
            action="send",
            device_id=device.id,
            parameters={"address": "/ping", "args": [1]},
        )
    )
    result = CueExecutionService(db_session).execute_cue(cue, dry_run=False)
    assert result.status == "executed"
    assert result.dry_run is True
