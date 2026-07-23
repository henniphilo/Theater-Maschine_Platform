from __future__ import annotations


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

    real = api_client.post(f"/api/v1/cues/{cue_id}/execute", json={"dry_run": False})
    assert real.status_code == 400

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
