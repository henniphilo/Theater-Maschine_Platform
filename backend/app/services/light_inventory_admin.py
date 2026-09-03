"""Operator light channel / inventory policy (Burgtheater channel blocks, group toggles)."""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.director.outputs.eos_light import expand_channels

logger = logging.getLogger(__name__)

_FILENAME = "light_channel_policy.json"
_INVENTORY_FILENAME = "light_inventory.json"
_lock = threading.Lock()
_cache: LightChannelPolicy | None = None
_persist_path_override: Path | None = None

# Burgtheater: these channels must not be driven by the machine.
DEFAULT_BLOCKED_CHANNELS: tuple[int, ...] = (11, 19, 22)


class LightInventoryGroup(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    channels: list[str] = Field(default_factory=list)
    fixtures: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=120)
    enabled: bool = True
    source: str = "catalog"  # catalog | extra

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()


class LightChannelPolicy(BaseModel):
    version: int = 1
    venue: str = "burgtheater"
    blocked_channels: list[int] = Field(default_factory=lambda: list(DEFAULT_BLOCKED_CHANNELS))
    disabled_inventory_group_ids: list[str] = Field(default_factory=list)
    extra_inventory_groups: list[LightInventoryGroup] = Field(default_factory=list)
    notes: str = ""

    @field_validator("blocked_channels")
    @classmethod
    def normalize_blocked(cls, value: list[int]) -> list[int]:
        cleaned = sorted({int(c) for c in value if int(c) > 0})
        return cleaned

    @field_validator("disabled_inventory_group_ids")
    @classmethod
    def normalize_disabled(cls, value: list[str]) -> list[str]:
        return sorted({v.strip().lower() for v in value if v and v.strip()})


class LightInventoryGroupCreateRequest(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    channels: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)  # unused for inventory; kept for UI symmetry
    fixtures: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=120)


class LightChannelPolicyPatchRequest(BaseModel):
    blocked_channels: list[int] | None = None
    disabled_inventory_group_ids: list[str] | None = None
    notes: str | None = None


class LightInventoryGroupEnabledPatch(BaseModel):
    enabled: bool


class LightInventoryAdminResponse(BaseModel):
    venue: str = ""
    source: str = ""
    blocked_channels: list[int]
    notes: str = ""
    groups: list[LightInventoryGroup]
    scenes: list[dict[str, Any]] = Field(default_factory=list)


def _slug_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    slug = normalized.strip("_")
    if not slug:
        raise ValueError("id darf nicht leer sein")
    if not re.match(r"^[a-z][a-z0-9_]*$", slug):
        slug = f"g_{slug}" if slug[0].isdigit() else slug
    if not re.match(r"^[a-z][a-z0-9_]*$", slug):
        raise ValueError(f"Ungültige id: {value!r}")
    return slug


def _data_dir() -> Path:
    configured = Path(settings.director_data_dir)
    if configured.is_absolute():
        return configured
    module_root = Path(__file__).resolve()
    for root in (module_root.parents[2], module_root.parents[1], Path.cwd()):
        candidate = root / configured
        if candidate.is_dir():
            return candidate
    return Path.cwd() / configured


def persist_path() -> Path:
    if _persist_path_override is not None:
        return _persist_path_override
    return _data_dir() / _FILENAME


def inventory_path() -> Path:
    return _data_dir() / _INVENTORY_FILENAME


def reset_light_policy_for_tests(persist_path: Path | None = None) -> None:
    global _cache, _persist_path_override
    with _lock:
        _cache = None
        _persist_path_override = persist_path


def load_policy(*, force: bool = False) -> LightChannelPolicy:
    global _cache
    with _lock:
        if _cache is not None and not force:
            return _cache
        path = persist_path()
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                _cache = LightChannelPolicy.model_validate(payload)
            except Exception as exc:
                logger.warning("light_channel_policy unreadable (%s): %s", path, exc)
                _cache = LightChannelPolicy()
        else:
            _cache = LightChannelPolicy()
        return _cache


def save_policy(data: LightChannelPolicy) -> LightChannelPolicy:
    global _cache
    path = persist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        path.write_text(
            json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _cache = data
    return data


def _load_inventory_raw() -> dict[str, Any]:
    path = inventory_path()
    if not path.is_file():
        return {"source": "", "venue": "", "groups": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("light_inventory unreadable (%s): %s", path, exc)
        return {"source": "", "venue": "", "groups": []}


def _save_inventory_raw(payload: dict[str, Any]) -> None:
    path = inventory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def effective_blocked_channels(*, policy: LightChannelPolicy | None = None) -> set[int]:
    """Channels that must not be sent to the desk (explicit block + disabled inventory groups)."""
    policy = policy or load_policy()
    blocked = set(policy.blocked_channels)
    inventory = _load_inventory_raw()
    groups_by_id = {
        str(g.get("id", "")).strip().lower(): g for g in inventory.get("groups", []) if g.get("id")
    }
    for extra in policy.extra_inventory_groups:
        groups_by_id[extra.id] = extra.model_dump()
    for group_id in policy.disabled_inventory_group_ids:
        group = groups_by_id.get(group_id)
        if not group:
            continue
        blocked.update(expand_channels(list(group.get("channels") or [])))
    return blocked


def filter_channel_list(channels: list[int], *, blocked: set[int] | None = None) -> list[int]:
    blocked = blocked if blocked is not None else effective_blocked_channels()
    return [c for c in channels if c not in blocked]


def expand_channels_respecting_policy(specs: list[str]) -> list[int]:
    return filter_channel_list(expand_channels(specs))


def list_inventory_groups(*, policy: LightChannelPolicy | None = None) -> list[LightInventoryGroup]:
    policy = policy or load_policy()
    disabled = set(policy.disabled_inventory_group_ids)
    inventory = _load_inventory_raw()
    rows: list[LightInventoryGroup] = []
    seen: set[str] = set()
    for raw in inventory.get("groups", []):
        gid = str(raw.get("id", "")).strip().lower()
        if not gid or gid in seen:
            continue
        rows.append(
            LightInventoryGroup(
                id=gid,
                channels=list(raw.get("channels") or []),
                fixtures=list(raw.get("fixtures") or []),
                location=str(raw.get("location") or ""),
                enabled=gid not in disabled,
                source="catalog",
            )
        )
        seen.add(gid)
    for extra in policy.extra_inventory_groups:
        if extra.id in seen:
            continue
        rows.append(
            extra.model_copy(update={"enabled": extra.id not in disabled, "source": "extra"})
        )
        seen.add(extra.id)
    return rows


def build_admin_response() -> LightInventoryAdminResponse:
    from app.director.media.database import MediaDatabase

    policy = load_policy()
    inventory = _load_inventory_raw()
    db = MediaDatabase()
    scenes = [
        {
            "id": s.id,
            "description": s.description,
            "channels": s.channels,
            "groups": s.groups,
        }
        for s in db.light_scenes
    ]
    return LightInventoryAdminResponse(
        venue=str(inventory.get("venue") or policy.venue or ""),
        source=str(inventory.get("source") or ""),
        blocked_channels=list(policy.blocked_channels),
        notes=policy.notes,
        groups=list_inventory_groups(policy=policy),
        scenes=scenes,
    )


def patch_policy(body: LightChannelPolicyPatchRequest) -> LightChannelPolicy:
    data = load_policy(force=True)
    updates: dict[str, Any] = {}
    if body.blocked_channels is not None:
        updates["blocked_channels"] = body.blocked_channels
    if body.disabled_inventory_group_ids is not None:
        updates["disabled_inventory_group_ids"] = body.disabled_inventory_group_ids
    if body.notes is not None:
        updates["notes"] = body.notes
    next_data = data.model_copy(update=updates)
    return save_policy(next_data)


def set_inventory_group_enabled(group_id: str, enabled: bool) -> LightInventoryGroup:
    gid = _slug_id(group_id)
    data = load_policy(force=True)
    disabled = set(data.disabled_inventory_group_ids)
    if enabled:
        disabled.discard(gid)
    else:
        disabled.add(gid)
    save_policy(data.model_copy(update={"disabled_inventory_group_ids": sorted(disabled)}))
    groups = {g.id: g for g in list_inventory_groups()}
    if gid not in groups:
        raise ValueError(f"Unbekannte Licht-Gruppe {gid!r}")
    return groups[gid]


def add_inventory_group(body: LightInventoryGroupCreateRequest) -> LightInventoryGroup:
    channels = [c.strip() for c in body.channels if c and str(c).strip()]
    if not channels:
        raise ValueError("Mindestens einen EOS-Channel angeben")
    # Validate expandable
    expand_channels(channels)
    gid = _slug_id(body.id or f"group_{channels[0]}")
    data = load_policy(force=True)
    existing_ids = {g.id for g in list_inventory_groups(policy=data)}
    if gid in existing_ids:
        raise ValueError(f"Licht-Gruppe {gid!r} existiert bereits")

    # Prefer persisting extras in inventory.json so MediaDatabase sees them
    inventory = _load_inventory_raw()
    inventory.setdefault("groups", []).append(
        {
            "id": gid,
            "channels": channels,
            "fixtures": list(body.fixtures),
            "location": body.location.strip(),
        }
    )
    _save_inventory_raw(inventory)

    # Keep MediaDatabase caches consistent if any
    from app.director.media.database import MediaDatabase

    try:
        MediaDatabase().reload()
    except Exception:
        pass

    return LightInventoryGroup(
        id=gid,
        channels=channels,
        fixtures=list(body.fixtures),
        location=body.location.strip(),
        enabled=True,
        source="catalog",
    )


def delete_inventory_group(group_id: str) -> None:
    """Delete only groups that were added (still in inventory file); catalog groups stay, use disable."""
    gid = _slug_id(group_id)
    inventory = _load_inventory_raw()
    groups = list(inventory.get("groups") or [])
    # Only allow delete if it's an "extra" tracked in policy, OR we allow removing any?
    # Safer: only remove from inventory if present; catalog edits are operator choice.
    remaining = [g for g in groups if str(g.get("id", "")).strip().lower() != gid]
    if len(remaining) == len(groups):
        raise ValueError(f"Licht-Gruppe {gid!r} nicht gefunden")
    inventory["groups"] = remaining
    _save_inventory_raw(inventory)

    data = load_policy(force=True)
    disabled = [x for x in data.disabled_inventory_group_ids if x != gid]
    extras = [g for g in data.extra_inventory_groups if g.id != gid]
    save_policy(
        data.model_copy(
            update={
                "disabled_inventory_group_ids": disabled,
                "extra_inventory_groups": extras,
            }
        )
    )
