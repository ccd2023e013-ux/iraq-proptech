"""Shared test fixtures.

Tests marked ``db`` need a real PostgreSQL + PostGIS (the same engine as
production — no SQLite stand-in). They use ``DATABASE_URL``. When the database
is unreachable they are skipped locally, but CI sets ``REQUIRE_DB=1`` so a
missing database is a hard failure there.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_JSON", "false")
# Tests exercise rate limiting explicitly (tests/test_rate_limit.py); elsewhere
# it would make results depend on test order.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("EMAIL_PROVIDER", "mock")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_LOCAL_PATH", tempfile.mkdtemp(prefix="proptech-test-storage-"))

from app.core.config import get_settings
from app.db.session import get_db, get_engine, get_sessionmaker
from app.main import create_app
from app.notifications.email import MockEmailProvider, get_email_provider

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


@pytest.fixture(scope="session")
def database_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        if os.environ.get("REQUIRE_DB") == "1":
            raise
        return False


@pytest.fixture(scope="session")
def migrated_db(database_available: bool) -> None:
    if not database_available:
        pytest.skip(f"database not reachable at {get_settings().database_url.split('@')[-1]}")
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def db_session(migrated_db: None) -> Iterator[Session]:
    """A session whose work is rolled back after each test."""
    connection = get_engine().connect()
    transaction = connection.begin()
    session = get_sessionmaker()(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    """Test client whose requests share the test's rolled-back DB session."""
    app = create_app()

    def override() -> Iterator[Session]:
        try:
            yield db_session
        except Exception:
            db_session.rollback()  # same semantics as the real get_db
            raise

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def mock_outbox() -> Iterator[MockEmailProvider]:
    provider = get_email_provider()
    assert isinstance(provider, MockEmailProvider)
    provider.clear()
    yield provider
    provider.clear()
