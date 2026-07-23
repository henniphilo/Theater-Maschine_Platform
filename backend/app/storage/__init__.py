"""Exchangeable object storage for production assets."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend, StorageError, StorageKeyError, StorageNotFoundError
from app.storage.local import LocalStorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend (MVP: local filesystem)."""
    return LocalStorageBackend(root=settings.resolved_storage_root())


def reset_storage_backend_cache() -> None:
    get_storage_backend.cache_clear()


__all__ = [
    "LocalStorageBackend",
    "StorageBackend",
    "StorageError",
    "StorageKeyError",
    "StorageNotFoundError",
    "get_storage_backend",
    "reset_storage_backend_cache",
]
