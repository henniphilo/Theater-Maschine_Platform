from __future__ import annotations

def test_api_create_list_get(api_client) -> None:
    create = api_client.post(
        "/api/v1/productions",
        json={"name": "Neue Produktion", "description": "MS1"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Neue Produktion"
    assert body["slug"] == "neue-produktion"
    assert body["status"] == "draft"
    assert body["archived_at"] is None

    listed = api_client.get("/api/v1/productions")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = api_client.get(f"/api/v1/productions/{body['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


def test_api_update_and_archive(api_client) -> None:
    created = api_client.post("/api/v1/productions", json={"name": "Edit me"}).json()
    patched = api_client.patch(
        f"/api/v1/productions/{created['id']}",
        json={"name": "Edited", "description": "desc"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Edited"

    archived = api_client.post(f"/api/v1/productions/{created['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None


def test_api_active_production(api_client) -> None:
    empty = api_client.get("/api/v1/productions/active")
    assert empty.status_code == 200
    assert empty.json()["production_id"] is None

    created = api_client.post("/api/v1/productions", json={"name": "Active One"}).json()
    set_resp = api_client.put(
        "/api/v1/productions/active",
        json={"production_id": created["id"]},
    )
    assert set_resp.status_code == 200
    assert set_resp.json()["production_id"] == created["id"]
    assert set_resp.json()["production"]["status"] == "active_eligible"

    got = api_client.get("/api/v1/productions/active")
    assert got.json()["production_id"] == created["id"]

    cleared = api_client.put("/api/v1/productions/active", json={"production_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["production_id"] is None


def test_api_cannot_activate_archived(api_client) -> None:
    created = api_client.post("/api/v1/productions", json={"name": "Arch"}).json()
    api_client.post(f"/api/v1/productions/{created['id']}/archive")
    resp = api_client.put(
        "/api/v1/productions/active",
        json={"production_id": created["id"]},
    )
    assert resp.status_code == 400


def test_api_not_found(api_client) -> None:
    resp = api_client.get("/api/v1/productions/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_legacy_health_unaffected(api_client) -> None:
    """Burgtheater/legacy smoke path must stay reachable beside Production API."""
    resp = api_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
