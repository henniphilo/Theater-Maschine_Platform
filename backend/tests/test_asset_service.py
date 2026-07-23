from __future__ import annotations

from pathlib import Path

from app.schemas.asset import AssetCreate, AssetUpdate
from app.schemas.production import ProductionCreate
from app.services.asset_service import (
    AssetNotFoundError,
    AssetService,
    AssetValidationError,
)
from app.services.production_service import ProductionService


def _production(db_session, active_store) -> str:
    return ProductionService(db_session).create_production(ProductionCreate(name="Lib")).id


def _payload(production_id: str, **overrides) -> AssetCreate:
    data = {
        "production_id": production_id,
        "name": "Clip A",
        "type": "video",
        "original_filename": "a.mp4",
        "storage_key": "p/a.mp4",
        "mime_type": "video/mp4",
        "size_bytes": 10,
        "checksum": "sha256:aa",
        "description": "desc",
        "metadata": {"tag": "open"},
    }
    data.update(overrides)
    return AssetCreate(**data)


def test_create_list_filter(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    other_id = ProductionService(db_session).create_production(ProductionCreate(name="Other")).id
    service = AssetService(db_session)

    video = service.create_asset(_payload(production_id))
    service.create_asset(
        _payload(
            production_id,
            name="Sound",
            type="audio",
            original_filename="a.wav",
            storage_key="p/a.wav",
            mime_type="audio/wav",
            checksum="sha256:bb",
        )
    )
    service.create_asset(_payload(other_id, name="Other clip", storage_key="o/a.mp4"))

    all_for_prod = service.list_assets(production_id=production_id)
    assert len(all_for_prod) == 2

    videos = service.list_assets(production_id=production_id, asset_type="video")
    assert len(videos) == 1
    assert videos[0].id == video.id


def test_update_metadata(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    service = AssetService(db_session)
    row = service.create_asset(_payload(production_id))

    updated = service.update_asset(
        row.id,
        AssetUpdate(name="Renamed", description=None, metadata={"tag": "close"}),
    )
    assert updated.name == "Renamed"
    assert updated.description is None
    assert updated.metadata_json == {"tag": "close"}
    assert updated.storage_key == "p/a.mp4"


def test_delete_removes_row_not_arbitrary_filesystem_path(
    db_session, active_store, storage_backend, tmp_path: Path
) -> None:
    """Legacy absolute storage_key must never unlink an arbitrary path."""
    production_id = _production(db_session, active_store)
    service = AssetService(db_session, storage=storage_backend)
    fake_file = tmp_path / "keep-me.bin"
    fake_file.write_bytes(b"payload")

    row = service.create_asset(
        _payload(production_id, storage_key=str(fake_file), name="Keep file")
    )
    service.delete_asset(row.id)

    try:
        service.get_asset(row.id)
        raised = False
    except AssetNotFoundError:
        raised = True
    assert raised is True
    assert fake_file.is_file()
    assert fake_file.read_bytes() == b"payload"


def test_create_rejects_unknown_production(db_session, active_store) -> None:
    service = AssetService(db_session)
    try:
        service.create_asset(_payload("00000000-0000-0000-0000-000000000000"))
        raised = False
    except AssetValidationError:
        raised = True
    assert raised is True


def test_invalid_type_filter(db_session, active_store) -> None:
    service = AssetService(db_session)
    try:
        service.list_assets(asset_type="not-a-type")
        raised = False
    except AssetValidationError:
        raised = True
    assert raised is True
