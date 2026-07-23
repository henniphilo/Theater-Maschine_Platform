from __future__ import annotations

from pathlib import Path

from app.schemas.asset import AssetCreate
from app.services.asset_service import AssetService


def _create_production(api_client) -> dict:
    resp = api_client.post("/api/v1/productions", json={"name": "Asset Show"})
    assert resp.status_code == 201
    return resp.json()


def _register_asset(
    db_session,
    *,
    production_id: str,
    name: str,
    asset_type: str,
    storage_key: str | None = None,
) -> str:
    row = AssetService(db_session).create_asset(
        AssetCreate(
            production_id=production_id,
            name=name,
            type=asset_type,  # type: ignore[arg-type]
            original_filename=f"{name}.bin",
            storage_key=storage_key or f"seed/{name}.bin",
            mime_type="application/octet-stream",
            size_bytes=42,
            checksum=f"seed-{name}",
            description="seeded",
            metadata={"source": "test"},
        )
    )
    return row.id


def test_api_list_filter_get_update_delete(api_client, db_session) -> None:
    production = _create_production(api_client)
    video_id = _register_asset(
        db_session, production_id=production["id"], name="Video", asset_type="video"
    )
    _register_asset(
        db_session, production_id=production["id"], name="Audio", asset_type="audio"
    )

    listed = api_client.get(f"/api/v1/assets?production_id={production['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert {row["id"] for row in listed.json()} >= {video_id}

    by_type = api_client.get(f"/api/v1/assets?production_id={production['id']}&type=video")
    assert by_type.status_code == 200
    assert len(by_type.json()) == 1
    assert by_type.json()[0]["id"] == video_id
    assert by_type.json()[0]["metadata"] == {"source": "test"}

    bad_type = api_client.get("/api/v1/assets?type=nope")
    assert bad_type.status_code == 400

    got = api_client.get(f"/api/v1/assets/{video_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "Video"

    patched = api_client.patch(
        f"/api/v1/assets/{video_id}",
        json={"name": "Video Renamed", "metadata": {"source": "edited"}},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Video Renamed"
    assert patched.json()["metadata"] == {"source": "edited"}

    deleted = api_client.delete(f"/api/v1/assets/{video_id}")
    assert deleted.status_code == 204

    missing = api_client.get(f"/api/v1/assets/{video_id}")
    assert missing.status_code == 404

    remaining = api_client.get(f"/api/v1/assets?production_id={production['id']}")
    assert remaining.status_code == 200
    assert len(remaining.json()) == 1


def test_api_delete_does_not_remove_arbitrary_filesystem_file(
    api_client, db_session, tmp_path: Path
) -> None:
    production = _create_production(api_client)
    fake = tmp_path / "must-remain.wav"
    fake.write_bytes(b"audio-bytes")

    asset_id = _register_asset(
        db_session,
        production_id=production["id"],
        name="Guard",
        asset_type="audio",
        storage_key=str(fake),
    )

    resp = api_client.delete(f"/api/v1/assets/{asset_id}")
    assert resp.status_code == 204
    assert fake.is_file()
    assert fake.read_bytes() == b"audio-bytes"


def test_api_not_found(api_client) -> None:
    resp = api_client.get("/api/v1/assets/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
