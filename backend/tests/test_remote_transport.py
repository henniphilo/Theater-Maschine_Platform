import time

from fastapi.testclient import TestClient

from app.director.remote_transport import (
    COMMAND_TTL_SEC,
    get_remote_transport_mailbox,
)
from app.core.config import settings
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    get_remote_transport_mailbox().reset()


def test_remote_transport_post_and_consume(monkeypatch):
    monkeypatch.setattr(settings, "director_enabled", True)
    post = client.post("/api/v1/director/remote-transport", json={"action": "play"})
    assert post.status_code == 200
    body = post.json()
    assert body["action"] == "play"
    assert body["id"]
    assert body["listener_connected"] is False

    peek = client.get("/api/v1/director/remote-transport")
    assert peek.status_code == 200
    assert peek.json()["pending"]["action"] == "play"

    consumed = client.get("/api/v1/director/remote-transport?consume=1&heartbeat=1")
    assert consumed.status_code == 200
    data = consumed.json()
    assert data["pending"]["id"] == body["id"]
    assert data["listener_connected"] is True

    empty = client.get("/api/v1/director/remote-transport?consume=1")
    assert empty.json()["pending"] is None


def test_remote_transport_overwrite_pending(monkeypatch):
    monkeypatch.setattr(settings, "director_enabled", True)
    client.post("/api/v1/director/remote-transport", json={"action": "play"})
    client.post("/api/v1/director/remote-transport", json={"action": "stop"})
    res = client.get("/api/v1/director/remote-transport?consume=1")
    assert res.json()["pending"]["action"] == "stop"


def test_remote_transport_stale_expiry(monkeypatch):
    monkeypatch.setattr(settings, "director_enabled", True)
    mailbox = get_remote_transport_mailbox()
    from app.director.remote_transport import RemoteTransportCommand

    with mailbox._lock:
        mailbox._pending = RemoteTransportCommand(
            id="stale",
            action="pause",
            created_at=time.monotonic() - COMMAND_TTL_SEC - 1,
        )
    snap = mailbox.snapshot(consume=True, heartbeat=False)
    assert snap["pending"] is None


def test_remote_transport_rejects_invalid_action(monkeypatch):
    monkeypatch.setattr(settings, "director_enabled", True)
    res = client.post("/api/v1/director/remote-transport", json={"action": "seek"})
    assert res.status_code == 422
