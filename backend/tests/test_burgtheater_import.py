"""Burgtheater importer — dry-run, idempotency, fixtures."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app.models.asset import Asset
from app.models.cue import Cue
from app.models.device import AdapterType, Device
from app.models.production import Production
from app.models.rule import Rule
from app.models.tag import Tag
from app.services.burgtheater_import import BurgtheaterImportOptions, run_burgtheater_import
from app.services.burgtheater_import import ids as import_ids

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "burgtheater_import"


def _options(*, dry_run: bool) -> BurgtheaterImportOptions:
    return BurgtheaterImportOptions(
        dry_run=dry_run,
        repo_root=FIXTURE_ROOT,
        data_dir=FIXTURE_ROOT / "data",
        media_dir=FIXTURE_ROOT / "media",
        copy_media_into_storage=True,
    )


def test_dry_run_does_not_persist(db_session, storage_backend) -> None:
    report = run_burgtheater_import(
        db_session,
        storage=storage_backend,
        options=_options(dry_run=True),
    )
    assert report.dry_run is True
    assert report.production_id is not None
    summary = report.to_dict()["summary"]
    assert summary["totals"]["planned"] > 0
    assert any(w.code == "missing_media" for w in report.warnings)
    assert any("MissingClip" in m or "missing_clip" in m for m in report.missing_media)

    # Rollback must leave DB empty.
    assert db_session.scalar(select(func.count()).select_from(Production)) == 0
    assert db_session.scalar(select(func.count()).select_from(Asset)) == 0
    assert db_session.scalar(select(func.count()).select_from(Cue)) == 0
    assert db_session.scalar(select(func.count()).select_from(Device)) == 0
    assert db_session.scalar(select(func.count()).select_from(Rule)) == 0


def test_apply_creates_production_assets_cues_devices_rules(db_session, storage_backend) -> None:
    report = run_burgtheater_import(
        db_session,
        storage=storage_backend,
        options=_options(dry_run=False),
    )
    assert report.dry_run is False
    assert report.production_slug == "burgtheater"

    production = db_session.scalar(
        select(Production).where(Production.slug == "burgtheater")
    )
    assert production is not None
    assert production.name == "Burgtheater"
    assert production.id == report.production_id

    assets = list(
        db_session.scalars(select(Asset).where(Asset.production_id == production.id)).all()
    )
    assert len(assets) >= 5
    assert any(a.metadata_json.get("legacy_id", "").startswith("burgtheater:asset:") for a in assets)

    cues = list(db_session.scalars(select(Cue).where(Cue.production_id == production.id)).all())
    cue_types = {c.cue_type for c in cues}
    assert "video" in cue_types
    assert "midi" in cue_types
    assert "light" in cue_types
    assert any(c.parameters.get("clip_id") == "affenslowodysee" for c in cues)
    assert any(c.action == "fade_blackout" for c in cues)

    devices = list(
        db_session.scalars(select(Device).where(Device.production_id == production.id)).all()
    )
    assert len(devices) == 4
    for device in devices:
        assert device.enabled is False
        assert device.adapter_type == AdapterType.DRY_RUN.value
        assert "host" not in device.configuration
        assert "port" not in device.configuration
        assert device.configuration.get("force_dry_run") is True

    rules = list(db_session.scalars(select(Rule).where(Rule.production_id == production.id)).all())
    assert len(rules) >= 4

    tags = list(db_session.scalars(select(Tag).where(Tag.production_id == production.id)).all())
    assert any(t.name == "drone" for t in tags)


def test_apply_is_idempotent(db_session, storage_backend) -> None:
    first = run_burgtheater_import(
        db_session,
        storage=storage_backend,
        options=_options(dry_run=False),
    )
    cue_count_1 = db_session.scalar(select(func.count()).select_from(Cue))
    asset_count_1 = db_session.scalar(select(func.count()).select_from(Asset))
    device_count_1 = db_session.scalar(select(func.count()).select_from(Device))
    rule_count_1 = db_session.scalar(select(func.count()).select_from(Rule))

    second = run_burgtheater_import(
        db_session,
        storage=storage_backend,
        options=_options(dry_run=False),
    )
    assert second.to_dict()["summary"]["totals"]["created"] == 0
    assert second.to_dict()["summary"]["totals"]["skipped"] > 0
    assert db_session.scalar(select(func.count()).select_from(Cue)) == cue_count_1
    assert db_session.scalar(select(func.count()).select_from(Asset)) == asset_count_1
    assert db_session.scalar(select(func.count()).select_from(Device)) == device_count_1
    assert db_session.scalar(select(func.count()).select_from(Rule)) == rule_count_1
    assert first.production_id == second.production_id


def test_stable_ids_and_checksum_duplicate_detection(db_session, storage_backend) -> None:
    run_burgtheater_import(
        db_session,
        storage=storage_backend,
        options=_options(dry_run=False),
    )
    legacy = import_ids.legacy_cue_video("affenslowodysee")
    cue_id = import_ids.stable_uuid(legacy)
    cue = db_session.get(Cue, cue_id)
    assert cue is not None
    assert cue.parameters["clip_id"] == "affenslowodysee"

    catalog_legacy = import_ids.legacy_asset_catalog("video_cues.json")
    asset = db_session.get(Asset, import_ids.stable_uuid(catalog_legacy))
    assert asset is not None
    assert asset.checksum.startswith("sha256:")
    assert asset.metadata_json.get("legacy_id") == catalog_legacy


def test_hardware_address_overlay_refused(db_session, storage_backend) -> None:
    options = _options(dry_run=False)
    options.include_hardware_addresses = True
    options.hardware_address_overlay = {
        "pixera": {"host": "10.0.0.1", "port": 7000},
    }
    report = run_burgtheater_import(db_session, storage=storage_backend, options=options)
    assert any(w.code == "hardware_address_skipped" for w in report.warnings)
    device = db_session.get(Device, import_ids.stable_uuid(import_ids.legacy_device("pixera")))
    assert device is not None
    assert "host" not in device.configuration
    assert "port" not in device.configuration
    assert device.configuration.get("label") == "pixera"


def test_sources_not_mutated(db_session, storage_backend) -> None:
    video_json = FIXTURE_ROOT / "data" / "video_cues.json"
    before = video_json.read_bytes()
    run_burgtheater_import(
        db_session,
        storage=storage_backend,
        options=_options(dry_run=False),
    )
    assert video_json.read_bytes() == before


def test_admin_api_dry_run_and_apply(api_client, storage_backend) -> None:
    dry = api_client.post(
        "/api/v1/admin/imports/burgtheater",
        json={
            "dry_run": True,
            "repo_root": str(FIXTURE_ROOT),
            "data_dir": str(FIXTURE_ROOT / "data"),
            "media_dir": str(FIXTURE_ROOT / "media"),
        },
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["dry_run"] is True
    assert body["summary"]["totals"]["planned"] > 0
    assert body["production_slug"] == "burgtheater"

    # Dry-run via API must not leave rows (same DB session override commits? service rolls back).
    listed = api_client.get("/api/v1/productions")
    assert listed.status_code == 200
    assert all(p["slug"] != "burgtheater" for p in listed.json())

    applied = api_client.post(
        "/api/v1/admin/imports/burgtheater",
        json={
            "dry_run": False,
            "repo_root": str(FIXTURE_ROOT),
            "data_dir": str(FIXTURE_ROOT / "data"),
            "media_dir": str(FIXTURE_ROOT / "media"),
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["dry_run"] is False
    listed2 = api_client.get("/api/v1/productions")
    assert any(p["slug"] == "burgtheater" for p in listed2.json())
