"""Storage backend protocol — keys only, never absolute local paths in callers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import BinaryIO, Protocol, runtime_checkable


class StorageError(Exception):
    """Base storage error."""


class StorageKeyError(StorageError):
    """Invalid or unsafe storage key."""


class StorageNotFoundError(StorageError):
    """Object does not exist for the given key."""


@runtime_checkable
class StorageBackend(Protocol):
    """Exchangeable blob store. Callers use opaque ``storage_key`` strings only."""

    def put_stream(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> int:
        """Write stream to ``key``. Returns byte count. Replaces existing objects."""

    def open_read(self, key: str) -> AbstractContextManager[BinaryIO]:
        """Open a readable binary stream for ``key``."""

    def exists(self, key: str) -> bool:
        """Return whether an object exists for ``key``."""

    def delete(self, key: str) -> None:
        """Delete object for ``key``. Raises ``StorageNotFoundError`` if missing."""
