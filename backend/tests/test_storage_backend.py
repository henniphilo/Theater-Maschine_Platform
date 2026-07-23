"""Unit tests for local storage keys and path safety."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.storage.base import StorageKeyError, StorageNotFoundError
from app.storage.filenames import UnsafeFilenameError, normalize_upload_filename
from app.storage.keys import assert_safe_storage_key, build_asset_storage_key
from app.storage.local import LocalStorageBackend


def test_normalize_rejects_traversal() -> None:
    with pytest.raises(UnsafeFilenameError):
        normalize_upload_filename("../secret.png")
    with pytest.raises(UnsafeFilenameError):
        normalize_upload_filename("foo/../../etc/passwd")
    with pytest.raises(UnsafeFilenameError):
        normalize_upload_filename("/abs/path.png")
    assert normalize_upload_filename("  Logo Final.PNG ") == "Logo Final.PNG"


def test_storage_key_rejects_escape(tmp_path: Path) -> None:
    backend = LocalStorageBackend(tmp_path)
    with pytest.raises(StorageKeyError):
        backend.put_stream("../outside.bin", io.BytesIO(b"x"))
    with pytest.raises(StorageKeyError):
        assert_safe_storage_key("/tmp/abs.bin")
    with pytest.raises(StorageKeyError):
        assert_safe_storage_key("productions/../etc/passwd")


def test_local_put_get_delete(tmp_path: Path) -> None:
    backend = LocalStorageBackend(tmp_path)
    key = build_asset_storage_key(
        production_id="prod-1",
        asset_id="asset-1",
        extension="png",
    )
    assert key == "productions/prod-1/assets/asset-1/original.png"
    backend.put_stream(key, io.BytesIO(b"abc"))
    assert backend.exists(key)
    with backend.open_read(key) as handle:
        assert handle.read() == b"abc"
    backend.delete(key)
    assert not backend.exists(key)
    with pytest.raises(StorageNotFoundError):
        backend.delete(key)
