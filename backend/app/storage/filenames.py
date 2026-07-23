"""Filename normalization and path-traversal checks for uploads."""

from __future__ import annotations

import re
import unicodedata

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_MAX_FILENAME_LENGTH = 200


class UnsafeFilenameError(ValueError):
    pass


def normalize_upload_filename(filename: str | None) -> str:
    """Return a safe basename. Rejects path traversal and empty names."""
    if filename is None:
        raise UnsafeFilenameError("filename is required")

    raw = unicodedata.normalize("NFC", filename.strip())
    if not raw:
        raise UnsafeFilenameError("filename must not be empty")

    # Reject any path-like input before taking basename.
    unified = raw.replace("\\", "/")
    if unified.startswith("/") or re.match(r"^[a-zA-Z]:/", unified):
        raise UnsafeFilenameError("absolute paths are not allowed")
    if "/" in unified or ".." in unified.split("/"):
        raise UnsafeFilenameError("path traversal is not allowed")

    name = unified.rsplit("/", 1)[-1]
    if name in ("", ".", ".."):
        raise UnsafeFilenameError("invalid filename")

    name = _CONTROL_RE.sub("", name)
    name = _WHITESPACE_RE.sub(" ", name).strip()
    name = name.replace("\0", "")
    if not name or name in (".", ".."):
        raise UnsafeFilenameError("filename must not be empty after normalization")

    if len(name) > _MAX_FILENAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        if dot and ext and len(ext) <= 20:
            keep = _MAX_FILENAME_LENGTH - len(ext) - 1
            name = f"{stem[:keep]}.{ext}"
        else:
            name = name[:_MAX_FILENAME_LENGTH]

    return name
