from __future__ import annotations

import pytest

from app.schemas.asset import AssetCreate
from app.schemas.production import ProductionCreate
from app.schemas.tag import TagCreate
from app.services.asset_service import AssetService
from app.services.production_service import ProductionService
from app.services.tag_service import (
    TagConflictError,
    TagNotFoundError,
    TagService,
    TagValidationError,
)


def _production(db_session, active_store) -> str:
    return ProductionService(db_session).create_production(ProductionCreate(name="Tags")).id


def _asset(db_session, production_id: str, name: str = "Clip") -> str:
    return AssetService(db_session).create_asset(
        AssetCreate(
            production_id=production_id,
            name=name,
            type="video",
            original_filename=f"{name}.mp4",
            storage_key=f"p/{name}.mp4",
            mime_type="video/mp4",
            size_bytes=10,
            checksum=f"sha256:{name}",
        )
    ).id


def test_create_list_delete_tag(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    service = TagService(db_session)

    tag = service.create_tag(TagCreate(production_id=production_id, name=" intro "))
    assert tag.name == "intro"

    listed = service.list_tags(production_id=production_id)
    assert len(listed) == 1
    assert listed[0].id == tag.id

    with pytest.raises(TagConflictError):
        service.create_tag(TagCreate(production_id=production_id, name="INTRO"))

    service.delete_tag(tag.id)
    assert service.list_tags(production_id=production_id) == []


def test_attach_detach_and_filter(db_session, active_store) -> None:
    production_id = _production(db_session, active_store)
    other_id = ProductionService(db_session).create_production(ProductionCreate(name="Other")).id
    tags = TagService(db_session)
    assets = AssetService(db_session)

    a1 = _asset(db_session, production_id, "One")
    a2 = _asset(db_session, production_id, "Two")
    a3 = _asset(db_session, production_id, "Three")
    _asset(db_session, other_id, "Other")

    intro = tags.create_tag(TagCreate(production_id=production_id, name="intro"))
    archive = tags.create_tag(TagCreate(production_id=production_id, name="archive"))
    other_tag = tags.create_tag(TagCreate(production_id=other_id, name="intro"))

    tags.attach_tag_to_asset(a1, tag_id=intro.id)
    tags.attach_tag_to_asset(a1, tag_id=archive.id)
    tags.attach_tag_to_asset(a2, name="intro")
    tags.attach_tag_to_asset(a3, tag_id=archive.id)

    with pytest.raises(TagValidationError):
        tags.attach_tag_to_asset(a1, tag_id=other_tag.id)

    only_intro = assets.list_assets(production_id=production_id, tag_ids=[intro.id])
    assert {row.id for row in only_intro} == {a1, a2}

    both = assets.list_assets(production_id=production_id, tag_ids=[intro.id, archive.id])
    assert {row.id for row in both} == {a1}

    updated = tags.detach_tag_from_asset(a1, intro.id)
    assert {t.name for t in updated.tags} == {"archive"}

    with pytest.raises(TagNotFoundError):
        tags.detach_tag_from_asset(a1, intro.id)
