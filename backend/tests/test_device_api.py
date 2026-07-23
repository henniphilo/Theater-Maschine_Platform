from __future__ import annotations


def _create_production(api_client, name: str = "Device API Show") -> dict:
    resp = api_client.post("/api/v1/productions", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def test_api_device_crud_default_dry_run_and_config_redaction(api_client) -> None:
    production = _create_production(api_client)

    created = api_client.post(
        "/api/v1/devices",
        json={
            "production_id": production["id"],
            "name": "Venue OSC",
            "configuration": {
                "host": "10.101.90.112",
                "port": 3032,
                "password": "super-secret",
                "notes": "desk",
            },
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["adapter_type"] == "dry_run"
    assert body["configuration"] == {"notes": "desk"}
    assert "host" not in body["configuration"]
    assert "password" not in body["configuration"]
    assert "password" in body["configuration_keys"]
    assert body["has_sensitive_configuration"] is True
    assert "configuration_sealed" not in body

    device_id = body["id"]

    listed = api_client.get(f"/api/v1/devices?production_id={production['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "host" not in listed.json()[0]["configuration"]

    tested = api_client.post(f"/api/v1/devices/{device_id}/test-connection")
    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    assert tested.json()["dry_run"] is True
    assert "host" not in tested.json().get("details", {})
    assert "password" not in tested.json().get("details", {})

    patched = api_client.patch(
        f"/api/v1/devices/{device_id}",
        json={"adapter_type": "osc", "name": "Venue OSC 2", "enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["adapter_type"] == "osc"
    assert patched.json()["enabled"] is False
    assert patched.json()["name"] == "Venue OSC 2"

    health = api_client.get(f"/api/v1/devices/{device_id}/health")
    assert health.status_code == 200
    assert "status" in health.json()

    deleted = api_client.delete(f"/api/v1/devices/{device_id}")
    assert deleted.status_code == 204

    missing = api_client.get(f"/api/v1/devices/{device_id}")
    assert missing.status_code == 404


def test_api_device_rejects_unknown_adapter(api_client) -> None:
    production = _create_production(api_client, "Device Bad Adapter")
    bad = api_client.post(
        "/api/v1/devices",
        json={
            "production_id": production["id"],
            "name": "Bad",
            "adapter_type": "qlab_relay",
        },
    )
    assert bad.status_code == 422
