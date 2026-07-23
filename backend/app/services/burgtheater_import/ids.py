"""Stable legacy IDs and deterministic UUIDs for idempotent Burgtheater import."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

PRODUCTION_NAME = "Burgtheater"
PRODUCTION_SLUG = "burgtheater"

# Fixed namespace — do not change; re-imports depend on stable UUIDs.
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://theatermaschine.local/import/burgtheater")


def legacy_production_id() -> str:
    return "burgtheater:production"


def legacy_asset_catalog(name: str) -> str:
    return f"burgtheater:asset:catalog:{name}"


def legacy_asset_clip(clip_id: str) -> str:
    return f"burgtheater:asset:clip:{clip_id}"


def legacy_asset_file(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    return f"burgtheater:asset:file:{normalized}"


def legacy_cue_video(clip_id: str) -> str:
    return f"burgtheater:cue:video:{clip_id}"


def legacy_cue_sound(cue_id: str) -> str:
    return f"burgtheater:cue:sound:{cue_id}"


def legacy_cue_light(scene_id: str) -> str:
    return f"burgtheater:cue:light:{scene_id}"


def legacy_device(role: str) -> str:
    return f"burgtheater:device:{role}"


def legacy_rule(canonical_id: str) -> str:
    return f"burgtheater:rule:{canonical_id}"


def legacy_tag(name: str) -> str:
    return f"burgtheater:tag:{name.strip().lower()}"


def stable_uuid(legacy_id: str) -> str:
    """Deterministic UUID string from a stable legacy key."""
    return str(uuid.uuid5(_NS, legacy_id))


def checksum_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def checksum_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return checksum_bytes(encoded)


def checksum_file(path: Any) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
