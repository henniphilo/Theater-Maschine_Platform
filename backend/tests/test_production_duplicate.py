from __future__ import annotations

from sqlalchemy import func, select

from app.director.cues.safety import get_safety_state
from app.models.asset import Asset
from app.models.cue import Cue
from app.models.production import ProductionStatus
from app.models.rule import Rule
from app.models.tag import Tag
from app.schemas.asset import AssetCreate
from app.schemas.cue import CueCreate
from app.schemas.device import DeviceCreate
from app.schemas.production import ProductionCreate
from app.schemas.rule import RuleCreate
from app.schemas.tag import TagCreate
from app.services.asset_service import AssetService
from app.services.cue_service import CueService
from app.services.device_service import DeviceService
from app.services.production_service import ProductionService
from app.services.rule_service import RuleService
from app.services.tag_service import TagService


def test_duplicate_shares_storage_and_copies_structure(db_session, active_store) -> None:
    prod = ProductionService(db_session).create_production(ProductionCreate(name="Source Show"))
    tag = TagService(db_session).create_tag(TagCreate(production_id=prod.id, name="intro"))
    asset = AssetService(db_session).create_asset(
        AssetCreate(
            production_id=prod.id,
            name="Clip",
            type="video",
            original_filename="a.mp4",
            storage_key="shared/key.mp4",
            mime_type="video/mp4",
            size_bytes=10,
            checksum="abc",
        )
    )
    TagService(db_session).attach_tag_to_asset(asset.id, tag_id=tag.id)
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            production_id=prod.id,
            name="Out",
            adapter_type="dry_run",
            enabled=True,
            configuration={},
        )
    )
    cue = CueService(db_session).create_cue(
        CueCreate(
            production_id=prod.id,
            name="Play",
            cue_type="video",
            action="play_clip",
            asset_id=asset.id,
            device_id=device.id,
            parameters={"clip_id": "a"},
        )
    )
    RuleService(db_session).create_rule(
        RuleCreate(
            production_id=prod.id,
            name="R",
            conditions=[{"type": "text_contains", "term": "x"}],
            actions=[{"type": "execute_cue", "cue_id": cue.id}],
        )
    )

    clone = ProductionService(db_session).duplicate_production(prod.id)
    assert clone.id != prod.id
    assert clone.status == ProductionStatus.DRAFT.value
    assert clone.name.endswith("(Kopie)")

    assert db_session.scalar(select(func.count()).select_from(Tag).where(Tag.production_id == clone.id)) == 1
    cloned_assets = list(
        db_session.scalars(select(Asset).where(Asset.production_id == clone.id)).all()
    )
    assert len(cloned_assets) == 1
    assert cloned_assets[0].storage_key == asset.storage_key
    assert cloned_assets[0].id != asset.id

    cloned_cues = list(db_session.scalars(select(Cue).where(Cue.production_id == clone.id)).all())
    assert len(cloned_cues) == 1
    assert cloned_cues[0].asset_id == cloned_assets[0].id
    assert cloned_cues[0].device_id != device.id

    cloned_rules = list(
        db_session.scalars(select(Rule).where(Rule.production_id == clone.id)).all()
    )
    assert cloned_rules[0].actions[0]["cue_id"] == cloned_cues[0].id

    # Source unchanged
    assert db_session.scalar(select(func.count()).select_from(Cue).where(Cue.production_id == prod.id)) == 1


def test_api_duplicate(api_client) -> None:
    production = api_client.post("/api/v1/productions", json={"name": "Dup Src"}).json()
    api_client.post(
        "/api/v1/cues",
        json={
            "production_id": production["id"],
            "name": "W",
            "cue_type": "wait",
            "action": "wait",
            "parameters": {"duration_seconds": 1},
        },
    )
    dup = api_client.post(f"/api/v1/productions/{production['id']}/duplicate", json={})
    assert dup.status_code == 201, dup.text
    assert dup.json()["id"] != production["id"]
    assert dup.json()["status"] == "draft"
    cues = api_client.get(f"/api/v1/cues?production_id={dup.json()['id']}")
    assert len(cues.json()) == 1


def test_active_switch_blocked_during_emergency(api_client) -> None:
    a = api_client.post("/api/v1/productions", json={"name": "A"}).json()
    b = api_client.post("/api/v1/productions", json={"name": "B"}).json()
    api_client.put("/api/v1/productions/active", json={"production_id": a["id"]})

    safety = get_safety_state()
    safety.emergency_stop()
    try:
        blocked = api_client.put("/api/v1/productions/active", json={"production_id": b["id"]})
        assert blocked.status_code == 400
        forced = api_client.put(
            "/api/v1/productions/active",
            json={"production_id": b["id"], "force": True},
        )
        assert forced.status_code == 200
        assert forced.json()["production_id"] == b["id"]
    finally:
        safety.clear_emergency_stop()
