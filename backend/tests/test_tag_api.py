from __future__ import annotations

from app.schemas.asset import AssetCreate
from app.services.asset_service import AssetService


def _create_production(api_client, name: str = "Tag Show") -> dict:
    resp = api_client.post("/api/v1/productions", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def _register_asset(db_session, *, production_id: str, name: str) -> str:
    return AssetService(db_session).create_asset(
        AssetCreate(
            production_id=production_id,
            name=name,
            type="video",
            original_filename=f"{name}.mp4",
            storage_key=f"seed/{name}.mp4",
            mime_type="video/mp4",
            size_bytes=10,
            checksum=f"seed-{name}",
        )
    ).id


def test_api_tag_crud_attach_filter(api_client, db_session) -> None:
    production = _create_production(api_client, "Tag Show A")
    other = _create_production(api_client, "Tag Show B")
    a1 = _register_asset(db_session, production_id=production["id"], name="One")
    a2 = _register_asset(db_session, production_id=production["id"], name="Two")

    created = api_client.post(
        "/api/v1/tags",
        json={"production_id": production["id"], "name": "intro"},
    )
    assert created.status_code == 201
    intro_id = created.json()["id"]

    duplicate = api_client.post(
        "/api/v1/tags",
        json={"production_id": production["id"], "name": "Intro"},
    )
    assert duplicate.status_code == 409

    listed = api_client.get(f"/api/v1/tags?production_id={production['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    attached = api_client.post(
        f"/api/v1/assets/{a1}/tags",
        json={"name": "archive"},
    )
    assert attached.status_code == 200
    assert {t["name"] for t in attached.json()["tags"]} == {"archive"}
    archive_id = attached.json()["tags"][0]["id"]

    attached2 = api_client.post(
        f"/api/v1/assets/{a1}/tags",
        json={"tag_id": intro_id},
    )
    assert attached2.status_code == 200
    assert {t["name"] for t in attached2.json()["tags"]} == {"archive", "intro"}

    api_client.post(f"/api/v1/assets/{a2}/tags", json={"tag_id": intro_id})

    filtered = api_client.get(
        f"/api/v1/assets?production_id={production['id']}&tag_id={intro_id}&tag_id={archive_id}"
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["id"] == a1

    foreign = api_client.post(
        "/api/v1/tags",
        json={"production_id": other["id"], "name": "foreign"},
    )
    assert foreign.status_code == 201
    cross = api_client.post(
        f"/api/v1/assets/{a1}/tags",
        json={"tag_id": foreign.json()["id"]},
    )
    assert cross.status_code == 400

    detached = api_client.delete(f"/api/v1/assets/{a1}/tags/{intro_id}")
    assert detached.status_code == 200
    assert {t["name"] for t in detached.json()["tags"]} == {"archive"}

    deleted = api_client.delete(f"/api/v1/tags/{archive_id}")
    assert deleted.status_code == 204

    got = api_client.get(f"/api/v1/assets/{a1}?production_id={production['id']}")
    assert got.status_code == 200
    assert got.json()["tags"] == []
