"""Active production runtime context.

Decision (MS1): persist the active production_id in a small JSON file under
``DIRECTOR_DATA_DIR`` (default ``data/active_production.json``).

Rationale:
- Exactly one active production per backend instance (PRD).
- Survives process restarts without a new DB table.
- Inspectable on disk; easy to clear in ops.
- Does not couple Burgtheater JSON stores to the new domain.

Not durable across multiple backend replicas (out of MVP scope).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from app.core.config import settings

_LOCK = threading.Lock()
_FILENAME = "active_production.json"


def _path() -> Path:
    return Path(settings.director_data_dir) / _FILENAME


def get_active_production_id() -> str | None:
    path = _path()
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get("production_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def set_active_production_id(production_id: str | None) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"production_id": production_id}
    with _LOCK:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def clear_active_production_id() -> None:
    set_active_production_id(None)


def reset_active_production_for_tests(tmp_dir: Path | None = None) -> None:
    """Point active-production storage at a temp dir (tests) or clear file."""
    if tmp_dir is not None:
        settings.director_data_dir = str(tmp_dir)
        return
    path = _path()
    if path.is_file():
        path.unlink()
