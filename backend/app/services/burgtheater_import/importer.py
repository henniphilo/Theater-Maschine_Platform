"""Burgtheater legacy → Production domain import (dry-run / apply, idempotent)."""

from __future__ import annotations

import json
import mimetypes
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetType
from app.models.cue import Cue, CueType
from app.models.device import AdapterType, Device
from app.models.production import Production, ProductionStatus
from app.models.rule import Rule
from app.models.tag import Tag
from app.services.burgtheater_import import ids
from app.services.burgtheater_import.report import ChangeKind, ImportReport
from app.services.burgtheater_import.sources import (
    DiscoveredSources,
    discover_sources,
    relative_to_root,
)
from app.services.cue_parameters import (
    validate_cue_action,
    validate_cue_parameters,
    validate_cue_type_requirements,
)
from app.services.rule_json_adapter import json_rules_to_canonical
from app.storage.base import StorageBackend
from app.storage.keys import build_asset_storage_key

# Sensitive / venue-bound keys must never be copied from settings or legacy overlays.
_HARDWARE_ADDRESS_KEYS = frozenset(
    {
        "host",
        "port",
        "tcp_host",
        "tcp_port",
        "osc_host",
        "osc_port",
        "midi_port",
        "ip",
        "address",
        "hostname",
        "password",
        "token",
        "api_key",
        "secret",
        "username",
        "auth",
        "credentials",
    }
)

_SOUND_ACTION_MAP: dict[str, tuple[str, str]] = {
    "play": (CueType.MIDI.value, "trigger_cue"),
    "fade_in": (CueType.MIDI.value, "trigger_cue"),
    "fade_out": (CueType.MIDI.value, "note_off"),
    "out": (CueType.MIDI.value, "note_off"),
}

_EXT_ASSET_TYPE: dict[str, str] = {
    ".mp4": AssetType.VIDEO.value,
    ".mov": AssetType.VIDEO.value,
    ".m4v": AssetType.VIDEO.value,
    ".webm": AssetType.VIDEO.value,
    ".mkv": AssetType.VIDEO.value,
    ".avi": AssetType.VIDEO.value,
    ".wav": AssetType.AUDIO.value,
    ".aiff": AssetType.AUDIO.value,
    ".aif": AssetType.AUDIO.value,
    ".mp3": AssetType.AUDIO.value,
    ".m4a": AssetType.AUDIO.value,
    ".png": AssetType.IMAGE.value,
    ".jpg": AssetType.IMAGE.value,
    ".jpeg": AssetType.IMAGE.value,
    ".webp": AssetType.IMAGE.value,
    ".txt": AssetType.TEXT.value,
    ".md": AssetType.TEXT.value,
    ".json": AssetType.DATA.value,
    ".csv": AssetType.DATA.value,
    ".xlsx": AssetType.DOCUMENT.value,
}


@dataclass
class BurgtheaterImportOptions:
    dry_run: bool = True
    repo_root: Path | None = None
    data_dir: Path | None = None
    media_dir: Path | None = None
    production_name: str = ids.PRODUCTION_NAME
    production_slug: str = ids.PRODUCTION_SLUG
    # Never take venue IPs/hosts unless explicitly requested (still not recommended).
    include_hardware_addresses: bool = False
    hardware_address_overlay: dict[str, Any] = field(default_factory=dict)
    copy_media_into_storage: bool = True


class BurgtheaterImporter:
    """Import Burgtheater reference data into a Production without mutating sources."""

    def __init__(
        self,
        db: Session,
        *,
        storage: StorageBackend | None = None,
        options: BurgtheaterImportOptions | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.options = options or BurgtheaterImportOptions()
        self._tag_cache: dict[str, Tag] = {}
        self._media_index: dict[str, Path] = {}

    def run(self) -> ImportReport:
        sources = discover_sources(
            repo_root=self.options.repo_root,
            data_dir=self.options.data_dir,
            media_dir=self.options.media_dir,
        )
        report = ImportReport(
            dry_run=self.options.dry_run,
            production_id=None,
            production_slug=self.options.production_slug,
            production_name=self.options.production_name,
            source_root=str(sources.repo_root),
        )
        try:
            self._build_media_index(sources)
            self._note_sources(report, sources)
            production = self._ensure_production(report)
            report.production_id = production.id

            self._import_catalog_assets(report, sources, production.id)
            self._import_csv_assets(report, sources, production.id)
            self._import_media_file_assets(report, sources, production.id)
            self._import_device_templates(report, sources, production.id)
            self._import_video_cues(report, sources, production.id)
            self._import_sound_cues(report, sources, production.id)
            self._import_light_cues(report, sources, production.id)
            self._import_rules(report, sources, production.id)

            if self.options.dry_run:
                self.db.rollback()
            else:
                self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return report

    # --- discovery helpers -------------------------------------------------

    def _note_sources(self, report: ImportReport, sources: DiscoveredSources) -> None:
        for name, path in sorted(sources.catalogs.items()):
            report.sources_seen.append(relative_to_root(path, sources.repo_root))
        for path in (sources.video_csv, sources.sound_csv, sources.projector_csv):
            if path is not None:
                report.sources_seen.append(relative_to_root(path, sources.repo_root))
        for path in sources.media_files:
            report.sources_seen.append(relative_to_root(path, sources.repo_root))

        for missing in sources.missing_expected:
            report.warn(
                "missing_source",
                f"Expected source not found: {missing}",
                path=missing,
                code_path=missing,
            )

    def _build_media_index(self, sources: DiscoveredSources) -> None:
        self._media_index.clear()
        for path in sources.media_files:
            slug = _slug_id(path.stem)
            self._media_index.setdefault(slug, path)
            pixera_like = _slug_id(path.stem.replace(" ", "").replace("_", ""))
            self._media_index.setdefault(pixera_like, path)

    # --- production --------------------------------------------------------

    def _ensure_production(self, report: ImportReport) -> Production:
        legacy = ids.legacy_production_id()
        entity_id = ids.stable_uuid(legacy)
        existing = self.db.get(Production, entity_id)
        if existing is None:
            by_slug = self.db.scalar(
                select(Production).where(Production.slug == self.options.production_slug)
            )
            if by_slug is not None:
                existing = by_slug

        desired_desc = (
            "Imported Burgtheater reference production (Unter Tieren). "
            "Sources under data/ and media/ were not modified."
        )
        change = self._change_verb()
        if existing is None:
            row = Production(
                id=entity_id,
                name=self.options.production_name,
                slug=self.options.production_slug,
                description=desired_desc,
                status=ProductionStatus.DRAFT.value,
            )
            if not self.options.dry_run:
                self.db.add(row)
                self.db.flush()
            else:
                self.db.add(row)
                self.db.flush()
            report.record(
                kind="production",
                change=change,
                legacy_id=legacy,
                entity_id=row.id,
                name=row.name,
            )
            return row

        updated = False
        if existing.name != self.options.production_name:
            existing.name = self.options.production_name
            updated = True
        if existing.description != desired_desc:
            existing.description = desired_desc
            updated = True
        if updated:
            existing.updated_at = datetime.now(timezone.utc)
            report.record(
                kind="production",
                change="planned" if self.options.dry_run else "updated",
                legacy_id=legacy,
                entity_id=existing.id,
                name=existing.name,
            )
        else:
            report.record(
                kind="production",
                change="skipped",
                legacy_id=legacy,
                entity_id=existing.id,
                name=existing.name,
            )
        return existing

    def _change_verb(self) -> ChangeKind:
        return "planned" if self.options.dry_run else "created"

    # --- assets ------------------------------------------------------------

    def _import_catalog_assets(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        for name, path in sorted(sources.catalogs.items()):
            legacy = ids.legacy_asset_catalog(name)
            payload = sources.catalog_payloads.get(name)
            checksum = ids.checksum_json(payload) if payload is not None else ids.checksum_file(path)
            self._upsert_file_asset(
                report,
                production_id=production_id,
                legacy_id=legacy,
                name=f"Catalog {name}",
                path=path,
                asset_type=AssetType.DATA.value,
                mime_type="application/json",
                checksum=checksum,
                metadata={
                    "legacy_id": legacy,
                    "source_kind": "catalog",
                    "source_path": relative_to_root(path, sources.repo_root),
                    "import_origin": "burgtheater",
                },
                description=f"Legacy catalog {name}",
                tags=["catalog", "burgtheater", Path(name).stem],
            )

    def _import_csv_assets(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        for label, path in (
            ("video_overview", sources.video_csv),
            ("sound_overview", sources.sound_csv),
            ("projector_overview", sources.projector_csv),
        ):
            if path is None:
                continue
            legacy = ids.legacy_asset_file(relative_to_root(path, sources.repo_root))
            self._upsert_file_asset(
                report,
                production_id=production_id,
                legacy_id=legacy,
                name=f"CSV {label}",
                path=path,
                asset_type=AssetType.DATA.value,
                mime_type="text/csv",
                checksum=ids.checksum_file(path),
                metadata={
                    "legacy_id": legacy,
                    "source_kind": "csv",
                    "source_path": relative_to_root(path, sources.repo_root),
                    "import_origin": "burgtheater",
                    "csv_role": label,
                },
                description=f"Legacy {label} CSV",
                tags=["csv", "burgtheater", label],
            )

    def _import_media_file_assets(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        for path in sources.media_files:
            # Skip CSVs already imported via dedicated CSV paths.
            if path.suffix.lower() == ".csv" and path in {
                sources.video_csv,
                sources.sound_csv,
                sources.projector_csv,
            }:
                continue
            rel = relative_to_root(path, sources.repo_root)
            legacy = ids.legacy_asset_file(rel)
            ext = path.suffix.lower()
            asset_type = _EXT_ASSET_TYPE.get(ext, AssetType.OTHER.value)
            mime, _ = mimetypes.guess_type(path.name)
            if mime is None:
                mime = "application/octet-stream"
            self._upsert_file_asset(
                report,
                production_id=production_id,
                legacy_id=legacy,
                name=path.name[:200],
                path=path,
                asset_type=asset_type,
                mime_type=mime,
                checksum=ids.checksum_file(path),
                metadata={
                    "legacy_id": legacy,
                    "source_kind": "media_file",
                    "source_path": rel,
                    "import_origin": "burgtheater",
                },
                description=f"Imported from {rel}",
                tags=["media", "burgtheater", path.parent.name],
            )

    def _upsert_file_asset(
        self,
        report: ImportReport,
        *,
        production_id: str,
        legacy_id: str,
        name: str,
        path: Path,
        asset_type: str,
        mime_type: str,
        checksum: str,
        metadata: dict[str, Any],
        description: str | None,
        tags: list[str],
    ) -> Asset | None:
        entity_id = ids.stable_uuid(legacy_id)
        existing = self.db.get(Asset, entity_id)
        size_bytes = path.stat().st_size if path.is_file() else 0
        storage_key = build_asset_storage_key(
            production_id=production_id,
            asset_id=entity_id,
            extension=_extension_for(path, mime_type),
        )
        meta = dict(metadata)
        meta["source_checksum"] = checksum

        if existing is None:
            row = Asset(
                id=entity_id,
                production_id=production_id,
                name=name[:200],
                type=asset_type,
                original_filename=path.name[:500],
                storage_key=storage_key,
                mime_type=mime_type[:200],
                size_bytes=size_bytes,
                checksum=checksum,
                description=description,
                metadata_json=meta,
            )
            self.db.add(row)
            self.db.flush()
            self._maybe_copy_to_storage(path, storage_key)
            self._attach_tags(row, production_id, tags)
            report.record(
                kind="asset",
                change=self._change_verb(),
                legacy_id=legacy_id,
                entity_id=entity_id,
                name=name,
            )
            return row

        identical = (
            existing.checksum == checksum
            and existing.name == name[:200]
            and existing.type == asset_type
        )
        if identical:
            report.record(
                kind="asset",
                change="skipped",
                legacy_id=legacy_id,
                entity_id=existing.id,
                name=existing.name,
            )
            return existing

        existing.name = name[:200]
        existing.type = asset_type
        existing.original_filename = path.name[:500]
        existing.storage_key = storage_key
        existing.mime_type = mime_type[:200]
        existing.size_bytes = size_bytes
        existing.checksum = checksum
        existing.description = description
        existing.metadata_json = meta
        existing.updated_at = datetime.now(timezone.utc)
        self._maybe_copy_to_storage(path, storage_key)
        self._attach_tags(existing, production_id, tags)
        report.record(
            kind="asset",
            change="planned" if self.options.dry_run else "updated",
            legacy_id=legacy_id,
            entity_id=existing.id,
            name=existing.name,
        )
        return existing

    def _maybe_copy_to_storage(self, path: Path, storage_key: str) -> None:
        if self.options.dry_run or not self.options.copy_media_into_storage:
            return
        if self.storage is None:
            return
        if not path.is_file():
            return
        with path.open("rb") as handle:
            self.storage.put_stream(storage_key, handle)

    def _attach_tags(self, asset: Asset, production_id: str, names: list[str]) -> None:
        for raw in names:
            tag = self._get_or_create_tag(production_id, raw)
            if tag is None:
                continue
            if tag not in asset.tags:
                asset.tags.append(tag)

    def _get_or_create_tag(self, production_id: str, name: str) -> Tag | None:
        cleaned = name.strip()
        if not cleaned:
            return None
        cleaned = cleaned[:100]
        cache_key = f"{production_id}:{cleaned.lower()}"
        if cache_key in self._tag_cache:
            return self._tag_cache[cache_key]

        legacy = ids.legacy_tag(cleaned)
        entity_id = ids.stable_uuid(legacy)
        existing = self.db.get(Tag, entity_id)
        if existing is None:
            existing = self.db.scalar(
                select(Tag).where(Tag.production_id == production_id, Tag.name == cleaned)
            )
        if existing is None:
            existing = Tag(id=entity_id, production_id=production_id, name=cleaned)
            self.db.add(existing)
            self.db.flush()
        self._tag_cache[cache_key] = existing
        return existing

    # --- devices -----------------------------------------------------------

    def _import_device_templates(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        projectors: list[dict[str, Any]] = []
        video_payload = sources.catalog_payloads.get("video_cues.json")
        if isinstance(video_payload, dict):
            raw = video_payload.get("projectors") or []
            if isinstance(raw, list):
                projectors = [p for p in raw if isinstance(p, dict)]

        templates = [
            {
                "role": "pixera",
                "name": "Burgtheater Pixera (template)",
                "intended_adapter": AdapterType.PIXERA.value,
                "configuration": {
                    "label": "pixera",
                    "notes": (
                        "Template only. Configure host/port manually before enabling. "
                        "Import did not copy venue network addresses."
                    ),
                    "intended_adapter_type": AdapterType.PIXERA.value,
                    "force_dry_run": True,
                    "output_slots": [
                        str(p.get("id")) for p in projectors if p.get("id")
                    ],
                    "projector_meta": [
                        {
                            "id": p.get("id"),
                            "name": p.get("name"),
                            "pixera_prefix": p.get("pixera_prefix"),
                        }
                        for p in projectors
                    ],
                },
            },
            {
                "role": "midi",
                "name": "Burgtheater Ableton MIDI (template)",
                "intended_adapter": AdapterType.MIDI.value,
                "configuration": {
                    "label": "midi",
                    "notes": "Template only. MIDI port must be configured locally.",
                    "intended_adapter_type": AdapterType.MIDI.value,
                    "force_dry_run": True,
                    "channel": 1,
                },
            },
            {
                "role": "eos_tcp",
                "name": "Burgtheater EOS Light (template)",
                "intended_adapter": AdapterType.EOS_TCP.value,
                "configuration": {
                    "label": "eos_tcp",
                    "notes": "Template only. Light desk host/port not imported.",
                    "intended_adapter_type": AdapterType.EOS_TCP.value,
                    "force_dry_run": True,
                    "protocol": "1.0",
                },
            },
            {
                "role": "osc",
                "name": "Burgtheater TouchDesigner OSC (template)",
                "intended_adapter": AdapterType.OSC.value,
                "configuration": {
                    "label": "touchdesigner_osc",
                    "notes": "Template only. OSC host/port not imported.",
                    "intended_adapter_type": AdapterType.OSC.value,
                    "force_dry_run": True,
                },
            },
        ]

        if self.options.include_hardware_addresses and self.options.hardware_address_overlay:
            report.warn(
                "hardware_addresses_requested",
                "include_hardware_addresses=true: overlay keys will be filtered to safe subset",
            )

        for template in templates:
            legacy = ids.legacy_device(str(template["role"]))
            entity_id = ids.stable_uuid(legacy)
            config = self._sanitize_device_config(dict(template["configuration"]))
            config["legacy_id"] = legacy
            config["import_origin"] = "burgtheater"

            if self.options.include_hardware_addresses:
                overlay = self.options.hardware_address_overlay.get(str(template["role"]))
                if isinstance(overlay, dict):
                    # Still strip secrets; only allow documented non-secret overlay after warn.
                    for key, value in overlay.items():
                        if str(key).lower() in _HARDWARE_ADDRESS_KEYS:
                            report.warn(
                                "hardware_address_skipped",
                                f"Refusing to import hardware key '{key}' for device {template['role']}",
                                legacy_id=legacy,
                                key=key,
                            )
                        else:
                            config[str(key)] = value

            existing = self.db.get(Device, entity_id)
            # Always dry_run adapter + disabled — never enable hardware from import.
            if existing is None:
                row = Device(
                    id=entity_id,
                    production_id=production_id,
                    name=str(template["name"])[:200],
                    adapter_type=AdapterType.DRY_RUN.value,
                    enabled=False,
                    configuration=config,
                    configuration_sealed=None,
                )
                self.db.add(row)
                self.db.flush()
                report.record(
                    kind="device",
                    change=self._change_verb(),
                    legacy_id=legacy,
                    entity_id=entity_id,
                    name=row.name,
                    detail="adapter=dry_run enabled=false",
                )
                continue

            identical = (
                existing.name == str(template["name"])[:200]
                and existing.adapter_type == AdapterType.DRY_RUN.value
                and existing.enabled is False
                and existing.configuration == config
            )
            if identical:
                report.record(
                    kind="device",
                    change="skipped",
                    legacy_id=legacy,
                    entity_id=existing.id,
                    name=existing.name,
                )
                continue

            existing.name = str(template["name"])[:200]
            existing.adapter_type = AdapterType.DRY_RUN.value
            existing.enabled = False
            existing.configuration = config
            existing.configuration_sealed = None
            existing.updated_at = datetime.now(timezone.utc)
            report.record(
                kind="device",
                change="planned" if self.options.dry_run else "updated",
                legacy_id=legacy,
                entity_id=existing.id,
                name=existing.name,
                detail="adapter=dry_run enabled=false",
            )

    def _sanitize_device_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in config.items():
            if str(key).lower() in _HARDWARE_ADDRESS_KEYS:
                continue
            cleaned[key] = value
        return cleaned

    # --- cues --------------------------------------------------------------

    def _import_video_cues(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        payload = sources.catalog_payloads.get("video_cues.json")
        if not isinstance(payload, dict):
            report.warn("missing_catalog", "video_cues.json missing or invalid")
            return
        clips = payload.get("clips") or []
        if not isinstance(clips, list):
            report.warn("invalid_catalog", "video_cues.json clips must be a list")
            return

        device_id = ids.stable_uuid(ids.legacy_device("pixera"))

        for clip in clips:
            if not isinstance(clip, dict) or not clip.get("id"):
                continue
            clip_id = str(clip["id"])
            legacy = ids.legacy_cue_video(clip_id)
            label = str(clip.get("label") or clip.get("pixera_name") or clip_id)
            video_type = str(clip.get("video_type") or "atmosphere")
            if video_type not in {"avatar", "atmosphere", "regie"}:
                video_type = "atmosphere"
            params = validate_cue_parameters(
                CueType.VIDEO.value,
                {
                    "clip_id": clip_id,
                    "projector": clip.get("projector_preference"),
                    "video_type": video_type,
                    "duration_ms": clip.get("duration_ms"),
                },
            )
            action = validate_cue_action(CueType.VIDEO.value, "play_clip")
            validate_cue_type_requirements(
                cue_type=CueType.VIDEO.value,
                action=action,
                parameters=params,
                asset_id=None,
            )

            media_path = self._find_media_for_clip(clip)
            if media_path is None:
                hint = clip.get("pixera_name") or clip_id
                missing = f"media/video/{hint}"
                if missing not in report.missing_media:
                    report.missing_media.append(missing)
                    report.warn(
                        "missing_media",
                        f"No local media file found for video clip '{clip_id}'",
                        path=missing,
                        legacy_id=legacy,
                        pixera_name=clip.get("pixera_name"),
                    )

            asset_id = None
            if media_path is not None:
                rel = relative_to_root(media_path, sources.repo_root)
                asset_id = ids.stable_uuid(ids.legacy_asset_file(rel))

            tag_names = [str(t) for t in (clip.get("tags") or []) if str(t).strip()]
            tag_names.extend(str(m) for m in (clip.get("moods") or []) if str(m).strip())
            tag_names.append("video")
            self._record_tags(report, production_id, tag_names)

            self._upsert_cue(
                report,
                production_id=production_id,
                legacy_id=legacy,
                name=label[:200],
                cue_type=CueType.VIDEO.value,
                action=action,
                parameters=params,
                asset_id=asset_id,
                device_id=device_id,
                enabled=True,
                priority=0,
            )

            # Virtual clip metadata asset (catalog entry) for searchability.
            clip_legacy = ids.legacy_asset_clip(clip_id)
            clip_checksum = ids.checksum_json(clip)
            self._upsert_virtual_asset(
                report,
                production_id=production_id,
                legacy_id=clip_legacy,
                name=f"Clip {label}"[:200],
                checksum=clip_checksum,
                payload=clip,
                tags=tag_names,
                description=str(clip.get("description") or ""),
            )

    def _import_sound_cues(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        payload = sources.catalog_payloads.get("sound_cues.json")
        if not isinstance(payload, dict):
            report.warn("missing_catalog", "sound_cues.json missing or invalid")
            return
        cues = payload.get("cues") or []
        if not isinstance(cues, list):
            report.warn("invalid_catalog", "sound_cues.json cues must be a list")
            return

        device_id = ids.stable_uuid(ids.legacy_device("midi"))
        for entry in cues:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            cue_id = str(entry["id"])
            legacy = ids.legacy_cue_sound(cue_id)
            raw_action = str(entry.get("action") or "play").strip().lower()
            cue_type, action = _SOUND_ACTION_MAP.get(
                raw_action, (CueType.MIDI.value, "trigger_cue")
            )
            midi_note = entry.get("midi_note")
            params_raw: dict[str, Any] = {
                "catalog_cue_id": cue_id,
                "channel": entry.get("channel") or 1,
                "velocity": entry.get("velocity") or 100,
                "note": midi_note,
            }
            action = validate_cue_action(cue_type, action)
            params = validate_cue_parameters(cue_type, params_raw)
            validate_cue_type_requirements(
                cue_type=cue_type,
                action=action,
                parameters=params,
                asset_id=None,
            )
            label = str(entry.get("label") or entry.get("soundname") or cue_id)
            tag_names = [str(t) for t in (entry.get("tags") or []) if str(t).strip()]
            tag_names.extend(str(m) for m in (entry.get("moods") or []) if str(m).strip())
            tag_names.append("sound")
            self._record_tags(report, production_id, tag_names)

            self._upsert_cue(
                report,
                production_id=production_id,
                legacy_id=legacy,
                name=f"{label} ({raw_action})"[:200],
                cue_type=cue_type,
                action=action,
                parameters=params,
                asset_id=None,
                device_id=device_id,
                enabled=bool(entry.get("dramaturgy_active", True)),
                priority=0,
            )

    def _import_light_cues(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        payload = sources.catalog_payloads.get("light_scenes.json")
        if not isinstance(payload, dict):
            report.warn("missing_catalog", "light_scenes.json missing or invalid")
            return
        scenes = payload.get("scenes") or []
        if not isinstance(scenes, list):
            report.warn("invalid_catalog", "light_scenes.json scenes must be a list")
            return

        device_id = ids.stable_uuid(ids.legacy_device("eos_tcp"))
        for scene in scenes:
            if not isinstance(scene, dict) or not scene.get("id"):
                continue
            scene_id = str(scene["id"])
            legacy = ids.legacy_cue_light(scene_id)
            if scene_id == "blackout":
                action = "fade_blackout"
                params_raw: dict[str, Any] = {
                    "scene_id": scene_id,
                    "fade_time": float(scene.get("fade_time") or 4.0),
                }
            else:
                action = "set_scene"
                params_raw = {
                    "scene_id": scene_id,
                    "fade_time": float(scene.get("fade_time") or 4.0),
                    "intensity": scene.get("intensity_max"),
                    "replace_previous": True,
                }
            action = validate_cue_action(CueType.LIGHT.value, action)
            params = validate_cue_parameters(CueType.LIGHT.value, params_raw)
            validate_cue_type_requirements(
                cue_type=CueType.LIGHT.value,
                action=action,
                parameters=params,
                asset_id=None,
            )
            label = str(scene.get("description") or scene_id)
            tag_names = [str(m) for m in (scene.get("moods") or []) if str(m).strip()]
            tag_names.append("light")
            self._record_tags(report, production_id, tag_names)

            self._upsert_cue(
                report,
                production_id=production_id,
                legacy_id=legacy,
                name=label[:200],
                cue_type=CueType.LIGHT.value,
                action=action,
                parameters=params,
                asset_id=None,
                device_id=device_id,
                enabled=True,
                priority=0,
            )

    def _upsert_cue(
        self,
        report: ImportReport,
        *,
        production_id: str,
        legacy_id: str,
        name: str,
        cue_type: str,
        action: str,
        parameters: dict[str, Any],
        asset_id: str | None,
        device_id: str | None,
        enabled: bool,
        priority: int,
    ) -> Cue:
        entity_id = ids.stable_uuid(legacy_id)
        existing = self.db.get(Cue, entity_id)
        if existing is None:
            row = Cue(
                id=entity_id,
                production_id=production_id,
                name=name,
                cue_type=cue_type,
                action=action,
                parameters=parameters,
                asset_id=asset_id,
                device_id=device_id,
                enabled=enabled,
                priority=priority,
            )
            self.db.add(row)
            self.db.flush()
            report.record(
                kind="cue",
                change=self._change_verb(),
                legacy_id=legacy_id,
                entity_id=entity_id,
                name=name,
            )
            return row

        identical = (
            existing.name == name
            and existing.cue_type == cue_type
            and existing.action == action
            and existing.parameters == parameters
            and existing.asset_id == asset_id
            and existing.device_id == device_id
            and existing.enabled == enabled
            and existing.priority == priority
        )
        if identical:
            report.record(
                kind="cue",
                change="skipped",
                legacy_id=legacy_id,
                entity_id=existing.id,
                name=existing.name,
            )
            return existing

        existing.name = name
        existing.cue_type = cue_type
        existing.action = action
        existing.parameters = parameters
        existing.asset_id = asset_id
        existing.device_id = device_id
        existing.enabled = enabled
        existing.priority = priority
        existing.updated_at = datetime.now(timezone.utc)
        report.record(
            kind="cue",
            change="planned" if self.options.dry_run else "updated",
            legacy_id=legacy_id,
            entity_id=existing.id,
            name=existing.name,
        )
        return existing

    def _upsert_virtual_asset(
        self,
        report: ImportReport,
        *,
        production_id: str,
        legacy_id: str,
        name: str,
        checksum: str,
        payload: dict[str, Any],
        tags: list[str],
        description: str,
    ) -> Asset:
        entity_id = ids.stable_uuid(legacy_id)
        storage_key = build_asset_storage_key(
            production_id=production_id,
            asset_id=entity_id,
            extension="json",
        )
        meta = {
            "legacy_id": legacy_id,
            "source_kind": "catalog_clip",
            "import_origin": "burgtheater",
            "source_checksum": checksum,
            "clip": payload,
        }
        blob = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        existing = self.db.get(Asset, entity_id)
        if existing is None:
            row = Asset(
                id=entity_id,
                production_id=production_id,
                name=name,
                type=AssetType.DATA.value,
                original_filename=f"{legacy_id.split(':')[-1]}.json",
                storage_key=storage_key,
                mime_type="application/json",
                size_bytes=len(blob),
                checksum=checksum,
                description=description[:2000] if description else None,
                metadata_json=meta,
            )
            self.db.add(row)
            self.db.flush()
            if not self.options.dry_run and self.storage is not None and self.options.copy_media_into_storage:
                from io import BytesIO

                self.storage.put_stream(storage_key, BytesIO(blob), content_type="application/json")
            self._attach_tags(row, production_id, tags)
            report.record(
                kind="asset",
                change=self._change_verb(),
                legacy_id=legacy_id,
                entity_id=entity_id,
                name=name,
                detail="virtual_clip",
            )
            return row

        if existing.checksum == checksum and existing.name == name:
            report.record(
                kind="asset",
                change="skipped",
                legacy_id=legacy_id,
                entity_id=existing.id,
                name=existing.name,
            )
            return existing

        existing.name = name
        existing.checksum = checksum
        existing.size_bytes = len(blob)
        existing.metadata_json = meta
        existing.description = description[:2000] if description else None
        existing.updated_at = datetime.now(timezone.utc)
        if not self.options.dry_run and self.storage is not None and self.options.copy_media_into_storage:
            from io import BytesIO

            self.storage.put_stream(storage_key, BytesIO(blob), content_type="application/json")
        self._attach_tags(existing, production_id, tags)
        report.record(
            kind="asset",
            change="planned" if self.options.dry_run else "updated",
            legacy_id=legacy_id,
            entity_id=existing.id,
            name=existing.name,
        )
        return existing

    def _find_media_for_clip(self, clip: dict[str, Any]) -> Path | None:
        candidates = [
            str(clip.get("id") or ""),
            str(clip.get("pixera_name") or ""),
            str(clip.get("label") or ""),
        ]
        for raw in candidates:
            if not raw:
                continue
            slug = _slug_id(raw)
            if slug in self._media_index:
                return self._media_index[slug]
            compact = _slug_id(raw.replace(" ", "").replace("_", "").replace("-", ""))
            if compact in self._media_index:
                return self._media_index[compact]
        return None

    def _record_tags(self, report: ImportReport, production_id: str, names: list[str]) -> None:
        seen: set[str] = set()
        for raw in names:
            cleaned = raw.strip()[:100]
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)

            legacy = ids.legacy_tag(cleaned)
            entity_id = ids.stable_uuid(legacy)
            prior = self.db.get(Tag, entity_id)
            if prior is None:
                prior = self.db.scalar(
                    select(Tag).where(Tag.production_id == production_id, Tag.name == cleaned)
                )

            tag = self._get_or_create_tag(production_id, cleaned)
            if tag is None:
                continue
            if prior is None:
                report.record(
                    kind="tag",
                    change=self._change_verb(),
                    legacy_id=legacy,
                    entity_id=tag.id,
                    name=tag.name,
                )
            else:
                # Avoid flooding the change log with every tag skip.
                report.ensure_counts("tag").bump("skipped")

    # --- rules -------------------------------------------------------------

    def _import_rules(
        self, report: ImportReport, sources: DiscoveredSources, production_id: str
    ) -> None:
        raw = sources.catalog_payloads.get("dramaturgy_rules.json")
        if not isinstance(raw, dict):
            report.warn("missing_catalog", "dramaturgy_rules.json missing or invalid")
            return

        canonical = json_rules_to_canonical(raw, production_id=production_id)
        for rule in canonical:
            legacy = ids.legacy_rule(rule.id)
            entity_id = ids.stable_uuid(legacy)
            conditions = [c.model_dump(mode="json", exclude_none=True) for c in rule.conditions]
            actions = [a.model_dump(mode="json", exclude_none=True) for a in rule.actions]
            name = rule.name[:200]
            existing = self.db.get(Rule, entity_id)
            if existing is None:
                row = Rule(
                    id=entity_id,
                    production_id=production_id,
                    name=name,
                    enabled=rule.enabled,
                    priority=rule.priority,
                    conditions=conditions,
                    actions=actions,
                    cooldown_seconds=rule.cooldown_seconds,
                )
                self.db.add(row)
                self.db.flush()
                report.record(
                    kind="rule",
                    change=self._change_verb(),
                    legacy_id=legacy,
                    entity_id=entity_id,
                    name=name,
                )
                continue

            identical = (
                existing.name == name
                and existing.enabled == rule.enabled
                and existing.priority == rule.priority
                and existing.conditions == conditions
                and existing.actions == actions
                and existing.cooldown_seconds == rule.cooldown_seconds
            )
            if identical:
                report.record(
                    kind="rule",
                    change="skipped",
                    legacy_id=legacy,
                    entity_id=existing.id,
                    name=existing.name,
                )
                continue

            existing.name = name
            existing.enabled = rule.enabled
            existing.priority = rule.priority
            existing.conditions = conditions
            existing.actions = actions
            existing.cooldown_seconds = rule.cooldown_seconds
            existing.updated_at = datetime.now(timezone.utc)
            report.record(
                kind="rule",
                change="planned" if self.options.dry_run else "updated",
                legacy_id=legacy,
                entity_id=existing.id,
                name=existing.name,
            )


def run_burgtheater_import(
    db: Session,
    *,
    storage: StorageBackend | None = None,
    options: BurgtheaterImportOptions | None = None,
) -> ImportReport:
    return BurgtheaterImporter(db, storage=storage, options=options).run()


def _extension_for(path: Path, mime_type: str) -> str:
    ext = path.suffix.lstrip(".").lower()
    if ext:
        return ext
    guessed = mimetypes.guess_extension(mime_type) or ".bin"
    return guessed.lstrip(".")


_UMLAUT_MAP = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"}
)


def _slug_id(stem: str) -> str:
    normalized = unicodedata.normalize("NFD", stem.strip())
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.translate(_UMLAUT_MAP).lower()
    normalized = re.sub(r"[^a-z0-9\-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")
