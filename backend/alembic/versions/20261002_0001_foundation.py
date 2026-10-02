"""Foundation: PostGIS + search extensions and system_settings.

Revision ID: 0001
Revises:
Create Date: 2026-10-02

Extensions are standard PostgreSQL contrib/PostGIS — available on the
postgis/postgis Docker image, on Supabase, and on any self-hosted server — so
the schema stays portable. On managed hosts where the role cannot create
extensions, enable them once from the provider dashboard and re-run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # fuzzy Arabic/English text search

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_system_settings")),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    # Extensions are intentionally left installed: other database objects or
    # the hosting provider may depend on them, and they are harmless.
