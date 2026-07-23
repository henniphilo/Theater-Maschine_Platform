from __future__ import annotations

from datetime import datetime

from app.models.asset import Asset, AssetType
from app.models.production import Production
from app.models.tag import Tag


def _seed_production(db_session) -> Production:
    row = Production(name="Tagged Show", slug="tagged-show")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_tag_model_and_asset_m2m(db_session) -> None:
    production = _seed_production(db_session)
    tag_a = Tag(production_id=production.id, name="intro")
    tag_b = Tag(production_id=production.id, name="archive")
    asset = Asset(
        production_id=production.id,
        name="Clip",
        type=AssetType.VIDEO.value,
        original_filename="clip.mp4",
        storage_key="p/clip.mp4",
        mime_type="video/mp4",
        size_bytes=10,
        checksum="x",
        metadata_json={},
    )
    db_session.add_all([tag_a, tag_b, asset])
    db_session.commit()
    db_session.refresh(asset)
    db_session.refresh(tag_a)

    asset.tags.extend([tag_a, tag_b])
    db_session.commit()
    db_session.refresh(asset)
    db_session.refresh(tag_a)

    assert {t.name for t in asset.tags} == {"intro", "archive"}
    assert len(tag_a.assets) == 1
    assert tag_a.assets[0].id == asset.id
    assert isinstance(tag_a.created_at, datetime)


def test_tag_unique_per_production(db_session) -> None:
    production = _seed_production(db_session)
    db_session.add(Tag(production_id=production.id, name="cue"))
    db_session.commit()

    db_session.add(Tag(production_id=production.id, name="cue"))
    raised = False
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raised = True
    assert raised is True
