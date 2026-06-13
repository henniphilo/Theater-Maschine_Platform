from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_director_dialogue_event_returns_decision() -> None:
    res = client.post(
        "/api/v1/director/dialogue-event",
        json={
            "speaker": "AI_A",
            "text": "Erinnerung ist vielleicht nur eine technische Störung.",
            "topic": "Erinnerung",
            "mood": "melancholisch",
            "intensity": 0.72,
            "tags": ["memory", "erinnerung"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["executed"] is False
    from app.director.media.database import MediaDatabase

    video_ids = {v.id for v in MediaDatabase().videos}
    assert body["decision"]["visual"]["clip_id"] in video_ids
    assert body["planned_commands"]
    assert body["osc_commands"] == []


def test_director_execute_returns_osc_commands() -> None:
    planned = client.post(
        "/api/v1/director/dialogue-event",
        json={
            "speaker": "AI_A",
            "text": "Erinnerung ist vielleicht nur eine technische Störung.",
            "topic": "Erinnerung",
            "mood": "melancholisch",
            "intensity": 0.72,
            "tags": ["memory", "erinnerung"],
        },
    ).json()

    res = client.post(
        "/api/v1/director/execute",
        json={"decision": planned["decision"], "stagger": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["executed"] is True
    assert body["osc_commands"]

    status = client.get("/api/v1/director/status").json()
    assert status["last_osc_commands"]


def test_director_status_and_safety_patch() -> None:
    status = client.get("/api/v1/director/status")
    assert status.status_code == 200
    assert "safety" in status.json()

    patched = client.patch(
        "/api/v1/director/safety",
        json={"autopilot_enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["safety"]["autopilot_enabled"] is False

    client.patch("/api/v1/director/safety", json={"autopilot_enabled": True})


def test_emergency_stop() -> None:
    res = client.post("/api/v1/director/emergency-stop")
    assert res.status_code == 200
    assert res.json()["safety"]["emergency_stop_active"] is True
    client.post("/api/v1/director/emergency-clear")
