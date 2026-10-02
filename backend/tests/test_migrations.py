"""Migrations are reversible and match the SQLAlchemy models exactly."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.migration_filters import compare_type, make_include_object
from app.db.models import Base
from app.db.session import get_engine
from tests.conftest import alembic_config

pytestmark = pytest.mark.db


def test_downgrade_and_upgrade_roundtrip(migrated_db: None) -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    assert "system_settings" not in inspect(get_engine()).get_table_names()
    command.upgrade(cfg, "head")
    assert "system_settings" in inspect(get_engine()).get_table_names()


def test_models_match_migrations(migrated_db: None) -> None:
    """Fails if someone changes a model without writing a migration."""
    with get_engine().connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"include_object": make_include_object(connection), "compare_type": compare_type},
        )
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"Models and migrations differ: {diff}"
