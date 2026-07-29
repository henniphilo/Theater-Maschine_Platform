from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.director.cues.cue_models import VisualCue
from app.director.cues.projector_state import ProjectorState
from app.schemas.device import DeviceCreate
from app.schemas.production import ProductionCreate
from app.services import active_production as active_production_store
from app.services.device_service import DeviceService
from app.services.output_slots import (
    LEGACY_OUTPUT_SLOTS,
    resolve_output_slots,
    slots_from_device_configuration,
)
from app.services.production_service import ProductionService


def test_slots_from_device_configuration() -> None:
    assert slots_from_device_configuration({"output_slots": ["left", "right", "left"]}) == (
        "left",
        "right",
    )
    assert slots_from_device_configuration(
        {"outputs": [{"id": "a"}, {"output_id": "b"}, "c"]}
    ) == ("a", "b", "c")


def test_resolve_output_slots_prefers_active_device(db_session, active_store) -> None:
    prod = ProductionService(db_session).create_production(ProductionCreate(name="Slots"))
    active_production_store.set_active_production_id(prod.id)
    DeviceService(db_session).create_device(
        DeviceCreate(
            production_id=prod.id,
            name="Pixera",
            adapter_type="dry_run",
            enabled=True,
            configuration={
                "output_slots": ["stage_l", "stage_r", "ceiling"],
                "atmosphere_free_slots": ["ceiling"],
                "force_dry_run": True,
            },
        )
    )
    assert resolve_output_slots(db_session) == ("stage_l", "stage_r", "ceiling")


def test_resolve_falls_back_to_legacy_without_active(db_session, active_store) -> None:
    active_production_store.clear_active_production_id()
    assert resolve_output_slots(db_session) == LEGACY_OUTPUT_SLOTS


def test_projector_state_custom_slots_atmosphere_free() -> None:
    state = ProjectorState()
    state.configure_slots(
        ("stage_l", "ceiling"),
        atmosphere_free_slots=frozenset({"ceiling"}),
    )
    now = datetime.now(UTC)
    avatar = VisualCue(
        clip_id="a",
        projector="stage_l",
        video_type="avatar",
        lock_until_finished=True,
        duration_ms=5000,
    )
    state.lock_after_play(avatar, now=now)
    atmos = VisualCue(clip_id="b", projector="ceiling", video_type="atmosphere")
    ok, reason = state.can_play(atmos, now=now + timedelta(milliseconds=10))
    assert ok is True
    assert reason is None

    blocked = VisualCue(clip_id="c", projector="stage_l", video_type="atmosphere")
    ok2, reason2 = state.can_play(blocked, now=now + timedelta(milliseconds=10))
    assert ok2 is False
    assert reason2 and "avatar_active" in reason2
