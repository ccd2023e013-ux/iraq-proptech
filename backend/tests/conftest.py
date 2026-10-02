"""Shared test fixtures.

Tests marked ``db`` need a real PostgreSQL + PostGIS (the same engine as
production — no SQLite stand-in). They use ``DATABASE_URL``. When the database
is unreachable they are skipped locally, but CI sets ``REQUIRE_DB=1`` so a
missing database is a hard failure there.
"""

from __future__ import annotations

import os
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

from app.core.config import get_settings
from app.db.session import get_engine, get_sessionmaker
from app.main import create_app

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
