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


def test_osc_test_send_visual_only() -> None:
    res = client.post(
        "/api/v1/director/osc-test",
        json={"send_visual": True, "send_sound": False, "send_light": False, "clip_id": "clyde", "stagger": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["executed"] is True
    assert {cmd["bridge"] for cmd in body["messages"]} == {"pixera"}


def test_light_desk_two_step_connect_then_send() -> None:
    connect = client.post("/api/v1/director/light/connect")
    assert connect.status_code == 200
    assert connect.json()["tcp_connected"] is True

    send = client.post(
        "/api/v1/director/light/send",
        json={"light_scene_id": "buehne_kalt_hart"},
    )
    assert send.status_code == 200
    assert send.json()["scene_id"] == "buehne_kalt_hart"

    stop = client.post("/api/v1/director/light/stop")
    assert stop.status_code == 200
    assert stop.json()["scene_id"] is None

    disconnect = client.post("/api/v1/director/light/disconnect")
    assert disconnect.status_code == 200
    assert disconnect.json()["tcp_connected"] is False


def test_light_send_without_connect_returns_409() -> None:
    client.post("/api/v1/director/light/disconnect")
    res = client.post(
        "/api/v1/director/light/send",
        json={"light_scene_id": "blendung_zuschauerraum"},
    )
    assert res.status_code == 409


def test_technik_start_rejects_light_channel() -> None:
    res = client.post(
        "/api/v1/director/technik/start",
        json={"send_visual": False, "send_sound": False, "send_light": True},
    )
    assert res.status_code == 400


def test_emergency_stop() -> None:
    res = client.post("/api/v1/director/emergency-stop")
    assert res.status_code == 200
    assert res.json()["safety"]["emergency_stop_active"] is True
    client.post("/api/v1/director/emergency-clear")
