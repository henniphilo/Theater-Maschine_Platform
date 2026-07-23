"""Asset upload / download / delete via StorageBackend."""

from __future__ import annotations

import io

import pytest

from app.core.config import settings


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _create_production(api_client) -> dict:
    resp = api_client.post("/api/v1/productions", json={"name": "Upload Show"})
    assert resp.status_code == 201
    return resp.json()


def test_upload_success_stores_file_and_checksum(api_client, storage_backend) -> None:
    production = _create_production(api_client)
    resp = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": production["id"], "name": "Logo"},
        files={"file": ("logo.png", PNG_1X1, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["production_id"] == production["id"]
    assert body["name"] == "Logo"
    assert body["type"] == "image"
    assert body["original_filename"] == "logo.png"
    assert body["mime_type"] == "image/png"
    assert body["size_bytes"] == len(PNG_1X1)
    assert body["checksum"].startswith("sha256:")
    assert body["storage_key"].startswith(f"productions/{production['id']}/assets/")
    assert body["storage_key"].endswith("/original.png")
    assert not body["storage_key"].endswith("logo.png")
    assert storage_backend.exists(body["storage_key"])

    content = api_client.get(
        f"/api/v1/assets/{body['id']}/content",
        params={"production_id": production["id"]},
    )
    assert content.status_code == 200
    assert content.content == PNG_1X1
    assert content.headers["content-type"].startswith("image/png")

    preview = api_client.get(
        f"/api/v1/assets/{body['id']}/preview",
        params={"production_id": production["id"]},
    )
    assert preview.status_code == 200
    assert preview.json()["kind"] == "image"
    assert preview.json()["preview_available"] is True


def test_upload_rejects_invalid_mime(api_client) -> None:
    production = _create_production(api_client)
    resp = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": production["id"]},
        files={"file": ("payload.exe", b"MZ\x90\x00not-an-image", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "mime" in resp.json()["detail"].lower() or "unrecognized" in resp.json()["detail"].lower()


def test_upload_rejects_oversized_file(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    production = _create_production(api_client)
    monkeypatch.setattr(settings, "asset_max_upload_bytes", 16)
    resp = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": production["id"]},
        files={"file": ("tiny.png", PNG_1X1, "image/png")},
    )
    assert resp.status_code == 400
    assert "maximum size" in resp.json()["detail"].lower()


def test_upload_rejects_path_traversal_filename(api_client) -> None:
    production = _create_production(api_client)
    resp = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": production["id"]},
        files={"file": ("../../etc/passwd.png", PNG_1X1, "image/png")},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "traversal" in detail or "path" in detail or "absolute" in detail


def test_aborted_upload_cleans_temp_and_skips_db(
    db_session, active_store, storage_backend
) -> None:
    from app.schemas.production import ProductionCreate
    from app.services.asset_service import AssetService
    from app.services.production_service import ProductionService

    production_id = ProductionService(db_session).create_production(
        ProductionCreate(name="Abort")
    ).id
    service = AssetService(db_session, storage=storage_backend)

    class FlakyStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:  # noqa: A003
            raise ConnectionError("client aborted")

    flaky = FlakyStream(PNG_1X1)
    before = [p for p in storage_backend.root.rglob("*") if p.is_file()]
    try:
        service.upload_asset(
            production_id=production_id,
            filename="logo.png",
            stream=flaky,
            content_type="image/png",
        )
        raised = False
    except ConnectionError:
        raised = True
    assert raised is True
    assert service.list_assets(production_id=production_id) == []
    after = [p for p in storage_backend.root.rglob("*") if p.is_file()]
    assert after == before


def test_delete_removes_storage_object(api_client, storage_backend) -> None:
    production = _create_production(api_client)
    uploaded = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": production["id"]},
        files={"file": ("logo.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 201
    asset = uploaded.json()
    assert storage_backend.exists(asset["storage_key"])

    deleted = api_client.delete(
        f"/api/v1/assets/{asset['id']}",
        params={"production_id": production["id"]},
    )
    assert deleted.status_code == 204
    assert not storage_backend.exists(asset["storage_key"])
    assert api_client.get(f"/api/v1/assets/{asset['id']}").status_code == 404


def test_cross_production_access_denied(api_client) -> None:
    prod_a = _create_production(api_client)
    prod_b = api_client.post("/api/v1/productions", json={"name": "Other"}).json()

    uploaded = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": prod_a["id"]},
        files={"file": ("logo.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]

    assert (
        api_client.get(
            f"/api/v1/assets/{asset_id}",
            params={"production_id": prod_b["id"]},
        ).status_code
        == 404
    )
    assert (
        api_client.get(
            f"/api/v1/assets/{asset_id}/content",
            params={"production_id": prod_b["id"]},
        ).status_code
        == 404
    )
    assert (
        api_client.get(
            f"/api/v1/assets/{asset_id}/preview",
            params={"production_id": prod_b["id"]},
        ).status_code
        == 404
    )
    assert (
        api_client.delete(
            f"/api/v1/assets/{asset_id}",
            params={"production_id": prod_b["id"]},
        ).status_code
        == 404
    )
    # Still reachable with the owning production
    assert (
        api_client.get(
            f"/api/v1/assets/{asset_id}",
            params={"production_id": prod_a["id"]},
        ).status_code
        == 200
    )


def test_text_preview(api_client) -> None:
    production = _create_production(api_client)
    payload = b'{"hello": "world"}\n'
    uploaded = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": production["id"]},
        files={"file": ("data.json", payload, "application/json")},
    )
    assert uploaded.status_code == 201, uploaded.text
    asset_id = uploaded.json()["id"]
    preview = api_client.get(
        f"/api/v1/assets/{asset_id}/preview",
        params={"production_id": production["id"]},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["kind"] == "json"
    assert "hello" in (body["text_excerpt"] or "")


def test_upload_unknown_production(api_client) -> None:
    resp = api_client.post(
        "/api/v1/assets/upload",
        data={"production_id": "00000000-0000-0000-0000-000000000000"},
        files={"file": ("logo.png", PNG_1X1, "image/png")},
    )
    assert resp.status_code == 400
