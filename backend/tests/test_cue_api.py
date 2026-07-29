from __future__ import annotations

from app.director.cues.safety import get_safety_state
from app.services.cue_execution_service import CueExecutionService, planned_to_adapter_command


def _create_production(api_client, name: str = "Cue API Show") -> dict:
    resp = api_client.post("/api/v1/productions", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def test_api_cue_crud_dry_run_and_legacy(api_client) -> None:
    production = _create_production(api_client)

    created = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "Wait Beat",
            "cue_type": "wait",
            "action": "wait",
            "parameters": {"duration_seconds": 2},
            "priority": 1,
        },
    )
    assert created.status_code == 201, created.text
    cue_id = created.json()["id"]
    assert created.json()["parameters"]["duration_seconds"] == 2

    bad = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "Bad OSC",
            "cue_type": "osc",
            "action": "send",
            "parameters": {"address": "pixera"},
        },
    )
    assert bad.status_code == 422

    listed = api_client.get(f"/api/v1/cues?production_id={production['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    dry = api_client.post(f"/api/v1/cues/{cue_id}/execute", json={"dry_run": True})
    assert dry.status_code == 200
    assert dry.json()["status"] == "planned"
    assert dry.json()["dry_run"] is True
    assert dry.json()["planned"]["director"]["wait"]["duration_seconds"] == 2

    # Wait cues may execute without a device (local, no hardware).
    real = api_client.post(f"/api/v1/cues/{cue_id}/execute", json={"dry_run": False})
    assert real.status_code == 200
    assert real.json()["status"] == "executed"
    assert real.json()["dry_run"] is False

    patched = api_client.patch(
        f"/api/v1/cues/{cue_id}",
        json={"name": "Wait Beat 2", "parameters": {"duration_seconds": 3}},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Wait Beat 2"

    legacy = api_client.get("/api/v1/cues/legacy")
    assert legacy.status_code == 200
    assert isinstance(legacy.json(), list)

    deleted = api_client.delete(f"/api/v1/cues/{cue_id}")
    assert deleted.status_code == 204

    missing = api_client.get(f"/api/v1/cues/{cue_id}")
    assert missing.status_code == 404


def test_api_video_cue_dry_run(api_client) -> None:
    production = _create_production(api_client, "Cue Video Show")
    created = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "Intro",
            "cue_type": "video",
            "action": "play_clip",
            "parameters": {"clip_id": "intro", "projector": "adam"},
        },
    )
    assert created.status_code == 201
    cue_id = created.json()["id"]

    dry = api_client.post(
        f"/api/v1/cues/{cue_id}/execute?production_id={production['id']}",
        json={"dry_run": True},
    )
    assert dry.status_code == 200
    assert dry.json()["planned"]["director"]["visual"]["action"] == "play_clip"

    # Video without device_id cannot real-execute.
    real = api_client.post(
        f"/api/v1/cues/{cue_id}/execute",
        json={"dry_run": False},
    )
    assert real.status_code == 400


def test_api_real_execute_via_dry_run_device(api_client) -> None:
    production = _create_production(api_client, "Cue Device Show")
    device = api_client.post(
        "/api/v1/devices",
        json={
            "production_id": production["id"],
            "name": "Safe Out",
            "adapter_type": "dry_run",
            "enabled": True,
            "configuration": {},
        },
    )
    assert device.status_code == 201, device.text
    device_id = device.json()["id"]

    created = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "OSC Ping",
            "cue_type": "osc",
            "action": "send",
            "device_id": device_id,
            "parameters": {"address": "/test/ping", "args": [1]},
        },
    )
    assert created.status_code == 201, created.text
    cue_id = created.json()["id"]

    real = api_client.post(f"/api/v1/cues/{cue_id}/execute", json={"dry_run": False})
    assert real.status_code == 200, real.text
    body = real.json()
    assert body["status"] == "executed"
    assert body["dry_run"] is True  # dry_run adapter always reports dry_run
    assert "would execute" in body["message"]


def test_api_disabled_device_skips_real(api_client) -> None:
    production = _create_production(api_client, "Disabled Dev Show")
    device = api_client.post(
        "/api/v1/devices",
        json={
            "production_id": production["id"],
            "name": "Off",
            "adapter_type": "dry_run",
            "enabled": False,
            "configuration": {},
        },
    ).json()
    cue = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "MIDI",
            "cue_type": "midi",
            "action": "note_on",
            "device_id": device["id"],
            "parameters": {"note": 60, "channel": 1, "velocity": 100},
        },
    ).json()

    real = api_client.post(f"/api/v1/cues/{cue['id']}/execute", json={"dry_run": False})
    assert real.status_code == 200
    assert real.json()["status"] == "skipped"
    assert "disabled" in real.json()["message"]


def test_api_emergency_blocks_real(api_client) -> None:
    production = _create_production(api_client, "Emergency Show")
    cue = api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "Wait",
            "cue_type": "wait",
            "action": "wait",
            "parameters": {"duration_seconds": 1},
        },
    ).json()

    safety = get_safety_state()
    safety.emergency_stop()
    try:
        real = api_client.post(f"/api/v1/cues/{cue['id']}/execute", json={"dry_run": False})
        assert real.status_code == 400
        assert "emergency" in real.json()["detail"].lower()
        # Dry-run still allowed during emergency (planning only).
        dry = api_client.post(f"/api/v1/cues/{cue['id']}/execute", json={"dry_run": True})
        assert dry.status_code == 200
        assert dry.json()["status"] == "planned"
    finally:
        safety.clear_emergency_stop()


def test_planned_to_adapter_command_merges_director(db_session, active_store) -> None:
    from app.schemas.cue import CueCreate
    from app.schemas.production import ProductionCreate
    from app.services.cue_compat import domain_cue_to_planned_payload
    from app.services.cue_service import CueService
    from app.services.production_service import ProductionService

    prod = ProductionService(db_session).create_production(ProductionCreate(name="Cmd"))
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=prod.id,
            name="V",
            cue_type="video",
            action="play_clip",
            parameters={"clip_id": "intro", "projector": "adam"},
        )
    )
    planned = domain_cue_to_planned_payload(cue)
    cmd = planned_to_adapter_command(cue, planned)
    assert cmd.action == "play_clip"
    assert cmd.params["clip_id"] == "intro"
    assert cmd.params["cue_id"] == cue.id


def test_service_execute_via_device(db_session, active_store) -> None:
    from app.schemas.cue import CueCreate
    from app.schemas.device import DeviceCreate
    from app.schemas.production import ProductionCreate
    from app.services.cue_service import CueService
    from app.services.device_service import DeviceService
    from app.services.production_service import ProductionService

    prod = ProductionService(db_session).create_production(ProductionCreate(name="Svc"))
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            production_id=prod.id,
            name="Dry",
            adapter_type="dry_run",
            enabled=True,
            configuration={},
        )
    )
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=prod.id,
            name="OSC",
            cue_type="osc",
            action="send",
            device_id=device.id,
            parameters={"address": "/a", "args": []},
        )
    )
    result = CueExecutionService(db_session).execute_cue(cue, dry_run=False)
    assert result.status == "executed"
    assert result.dry_run is True
