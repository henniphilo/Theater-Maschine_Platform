"""Shared DB fixtures for Production domain tests (SQLite in-memory — no Postgres required)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app
from app.models import asset as asset_model  # noqa: F401
from app.models import production as production_model  # noqa: F401
from app.models import tag as tag_model  # noqa: F401
from app.services import active_production as active_production_store
from app.storage import get_storage_backend, reset_storage_backend_cache
from app.storage.local import LocalStorageBackend


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def active_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(active_production_store.settings, "director_data_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def storage_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalStorageBackend:
    root = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", str(root))
    monkeypatch.setattr(settings, "asset_max_upload_bytes", 1024 * 1024)
    reset_storage_backend_cache()
    backend = LocalStorageBackend(root)
    yield backend
    reset_storage_backend_cache()


@pytest.fixture()
def api_client(
    db_engine, active_store: Path, storage_backend: LocalStorageBackend
) -> Generator[TestClient, None, None]:
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_backend] = lambda: storage_backend
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_storage_backend, None)
        client.close()
