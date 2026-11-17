"""Root Pytest Conftest and Global Integrity Guard for FRAMEOPS.

Safeguards:
1. Root autouse session guard fixture asserting SHA-256 of backend/frameops.db is unchanged before and after the test session.
2. In-memory isolated database fixture (`isolated_db`) using `sqlite://` with `StaticPool` and monkeypatching `app.db.engine`, `app.db.SessionLocal`, and router references.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db
import app.models
from app.config import settings
from app.db import Base, get_db
from app.main import app as fastapi_app
try:
    import app.routers.feedback as feedback_router
except ImportError:
    feedback_router = None


def _find_prod_db_path() -> Path | None:
    """Locate backend/frameops.db from current working directory or relative path."""
    candidates = [
        Path.cwd() / "backend" / "frameops.db",
        Path.cwd() / "frameops.db",
        Path(__file__).resolve().parent.parent / "frameops.db",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _calculate_db_sha256(path: Path | None) -> str | None:
    """Computes SHA-256 digest of the SQLite database file."""
    if path is None or not path.is_file():
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def guard_production_db() -> Generator[None, None, None]:
    """Root autouse session guard fixture asserting backend/frameops.db remains 100% untouched."""
    db_path = _find_prod_db_path()
    initial_sha = _calculate_db_sha256(db_path)
    initial_size = db_path.stat().st_size if db_path and db_path.is_file() else None

    yield

    final_sha = _calculate_db_sha256(db_path)
    final_size = db_path.stat().st_size if db_path and db_path.is_file() else None

    if initial_sha is not None:
        assert initial_sha == final_sha, (
            f"CRITICAL INTEGRITY VIOLATION: backend/frameops.db was modified during the test session!\n"
            f"Initial SHA-256: {initial_sha} (size: {initial_size} bytes)\n"
            f"Final SHA-256:   {final_sha} (size: {final_size} bytes)"
        )


@pytest.fixture(autouse=True)
def isolate_rate_limiter_and_revocations() -> Generator[None, None, None]:
    """Ensures each test has an isolated rate-limiter and revocation state."""
    from app.security import auth_rate_limiter, token_revocation_store

    auth_rate_limiter.reset()
    token_revocation_store.reset()
    yield
    auth_rate_limiter.reset()
    token_revocation_store.reset()


@pytest.fixture
def isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[sessionmaker[Session], None, None]:
    """Provides an isolated in-memory SQLite database for the test duration.
    
    Monkeypatches app.db.engine, app.db.SessionLocal, app.routers.feedback.SessionLocal,
    and app.dependency_overrides[get_db].
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        with TestSessionLocal() as session:
            yield session

    test_upload_dir = tmp_path / "uploads"
    test_upload_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "auth_secret", "conftest-isolated-secret-with-sufficient-entropy-123456789")
    monkeypatch.setattr(settings, "upload_dir", str(test_upload_dir))
    monkeypatch.setattr(app.db, "engine", test_engine)
    monkeypatch.setattr(app.db, "SessionLocal", TestSessionLocal)

    if feedback_router is not None and hasattr(feedback_router, "SessionLocal"):
        monkeypatch.setattr(feedback_router, "SessionLocal", TestSessionLocal)

    fastapi_app.dependency_overrides[get_db] = override_get_db

    yield TestSessionLocal

    fastapi_app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()
