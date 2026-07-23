"""Device configuration sealing and API redaction.

Sensitive connection values are never returned by read APIs. Storage supports an
HMAC-sealed envelope when ``DEVICE_CONFIG_KEY`` is set (integrity + obscurity).
Full AEAD encryption can replace the seal format later without changing callers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings

# Keys that must never appear in API responses.
SENSITIVE_CONFIG_KEYS = frozenset(
    {
        "host",
        "port",
        "password",
        "token",
        "api_key",
        "secret",
        "username",
        "midi_port",
        "auth",
        "credentials",
    }
)

PUBLIC_CONFIG_KEYS = frozenset(
    {
        "label",
        "notes",
        "channel",
        "force_dry_run",
        "protocol",
        "framing",
        "format",
    }
)

_SEAL_PREFIX_PLAIN = "plain:"
_SEAL_PREFIX_HMAC = "hmac1:"


def is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    if lowered in SENSITIVE_CONFIG_KEYS:
        return True
    return any(
        token in lowered
        for token in ("password", "secret", "token", "api_key", "credential")
    )


def split_configuration(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (public_subset, full_normalized)."""
    full: dict[str, Any] = {}
    public: dict[str, Any] = {}
    for key, value in config.items():
        if not isinstance(key, str) or not key.strip():
            continue
        name = key.strip()
        full[name] = value
        if not is_sensitive_key(name):
            public[name] = value
    return public, full


def redact_configuration(config: dict[str, Any] | None) -> dict[str, Any]:
    """Public-safe view: sensitive keys omitted entirely."""
    if not config:
        return {}
    return {k: v for k, v in config.items() if isinstance(k, str) and not is_sensitive_key(k)}


def configuration_key_names(config: dict[str, Any] | None) -> list[str]:
    if not config:
        return []
    return sorted(str(k) for k in config.keys())


def _device_config_key() -> str | None:
    key = (getattr(settings, "device_config_key", None) or "").strip()
    return key or None


def seal_configuration(full: dict[str, Any]) -> str:
    """Serialize full config into a sealed blob (not for API responses)."""
    payload = json.dumps(full, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    key = _device_config_key()
    if key is None:
        return f"{_SEAL_PREFIX_PLAIN}{encoded}"
    digest = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{_SEAL_PREFIX_HMAC}{digest}.{encoded}"


def unseal_configuration(sealed: str | None, *, public_fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Restore full configuration from seal; fall back to public JSON column."""
    if not sealed:
        return dict(public_fallback or {})

    if sealed.startswith(_SEAL_PREFIX_PLAIN):
        raw = base64.urlsafe_b64decode(sealed[len(_SEAL_PREFIX_PLAIN) :].encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("sealed configuration must be a JSON object")
        return data

    if sealed.startswith(_SEAL_PREFIX_HMAC):
        body = sealed[len(_SEAL_PREFIX_HMAC) :]
        digest, _, encoded = body.partition(".")
        if not digest or not encoded:
            raise ValueError("invalid hmac seal format")
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        key = _device_config_key()
        if key is None:
            raise ValueError("DEVICE_CONFIG_KEY required to unseal hmac configuration")
        expected = hmac.new(key.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, expected):
            raise ValueError("sealed configuration integrity check failed")
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("sealed configuration must be a JSON object")
        return data

    raise ValueError("unknown sealed configuration format")


def pack_for_storage(config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return (public_json_column, sealed_blob) for persistence."""
    public, full = split_configuration(config)
    return public, seal_configuration(full)


def unpack_from_storage(
    *,
    configuration: dict[str, Any] | None,
    configuration_sealed: str | None,
) -> dict[str, Any]:
    return unseal_configuration(configuration_sealed, public_fallback=configuration)
