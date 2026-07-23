"""Local filesystem storage backend — paths stay inside this module."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageKeyError, StorageNotFoundError
from app.storage.keys import assert_safe_storage_key


class LocalStorageBackend:
    """Store objects under ``root`` using relative storage keys only."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, key: str) -> Path:
        assert_safe_storage_key(key)
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise StorageKeyError(f"storage key escapes root: {key}") from exc
        return candidate

    def put_stream(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> int:
        _ = content_type  # reserved for S3/MinIO metadata
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_name = tempfile.mkstemp(prefix=".upload-", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        size = 0
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    size += len(chunk)
            os.replace(tmp_path, target)
            return size
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    @contextmanager
    def open_read(self, key: str) -> Iterator[BinaryIO]:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageNotFoundError(f"object not found: {key}")
        with path.open("rb") as handle:
            yield handle

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except StorageKeyError:
            return False

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageNotFoundError(f"object not found: {key}")
        path.unlink()
        # Best-effort cleanup of empty asset directories.
        parent = path.parent
        for _ in range(3):
            if parent == self._root or not parent.exists():
                break
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
