"""Storage key helpers — opaque relative keys, no user-controlled paths."""

from __future__ import annotations

from pathlib import PurePosixPath

from app.storage.base import StorageKeyError

_MAX_KEY_LENGTH = 512


def assert_safe_storage_key(key: str) -> None:
    """Reject absolute paths, traversal, and empty segments."""
    if not key or not key.strip():
        raise StorageKeyError("storage key must not be empty")
    if len(key) > _MAX_KEY_LENGTH:
        raise StorageKeyError("storage key too long")
    if key.startswith("/") or key.startswith("\\"):
        raise StorageKeyError("storage key must be relative")
    if "\\" in key:
        raise StorageKeyError("storage key must use forward slashes")
    if ":" in key.split("/")[0]:
        # Windows drive / URL-like schemes
        raise StorageKeyError("storage key must not contain a scheme or drive")

    parts = PurePosixPath(key).parts
    if not parts:
        raise StorageKeyError("storage key must not be empty")
    for part in parts:
        if part in ("", ".", ".."):
            raise StorageKeyError("storage key contains illegal path segment")


def build_asset_storage_key(*, production_id: str, asset_id: str, extension: str) -> str:
    """Server-generated key: productions/<pid>/assets/<aid>/original.<ext>."""
    ext = extension.lstrip(".").lower()
    if not ext or "/" in ext or "\\" in ext or ext in (".", ".."):
        raise StorageKeyError("invalid extension for storage key")
    for value, label in ((production_id, "production_id"), (asset_id, "asset_id")):
        if not value or "/" in value or "\\" in value or ".." in value:
            raise StorageKeyError(f"invalid {label} for storage key")
    key = f"productions/{production_id}/assets/{asset_id}/original.{ext}"
    assert_safe_storage_key(key)
    return key
