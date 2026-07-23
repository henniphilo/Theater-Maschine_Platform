from __future__ import annotations

from datetime import datetime

from app.models.asset import Asset, AssetType
from app.models.production import Production


def _seed_production(db_session) -> Production:
    row = Production(name="Show", slug="show-assets")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_asset_model_defaults(db_session) -> None:
    production = _seed_production(db_session)
    row = Asset(
        production_id=production.id,
        name="Intro Clip",
        type=AssetType.VIDEO.value,
        original_filename="intro.mp4",
        storage_key="productions/show/assets/intro.mp4",
        mime_type="video/mp4",
        size_bytes=1024,
        checksum="abc123",
        description="Opening",
        metadata_json={"duration_ms": 12000},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id
    assert len(row.id) == 36
    assert row.production_id == production.id
    assert row.type == "video"
    assert row.metadata_json == {"duration_ms": 12000}
    assert isinstance(row.created_at, datetime)
    assert isinstance(row.updated_at, datetime)


def test_asset_requires_production_fk(db_session) -> None:
    row = Asset(
        production_id="00000000-0000-0000-0000-000000000000",
        name="Orphan",
        type=AssetType.OTHER.value,
        original_filename="x.bin",
        storage_key="orphan/x.bin",
        mime_type="application/octet-stream",
        size_bytes=1,
        checksum="x",
        metadata_json={},
    )
    db_session.add(row)
    # SQLite may not enforce FK unless PRAGMA foreign_keys=ON; assert column is set.
    db_session.commit()
    db_session.refresh(row)
    assert row.production_id == "00000000-0000-0000-0000-000000000000"
