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
    assert body["executed"] is True
    assert body["decision"]["visual"]["clip_id"] == "memory_noise_03"


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
