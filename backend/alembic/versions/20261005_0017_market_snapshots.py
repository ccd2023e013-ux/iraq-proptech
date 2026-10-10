"""Market Intelligence: daily market snapshots.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("property_type_code", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("include_demo", sa.Boolean(), nullable=False),
        sa.Column("active_listings", sa.Integer(), nullable=False),
        sa.Column("demo_listings", sa.Integer(), nullable=False),
        sa.Column("priced_listings", sa.Integer(), nullable=False),
        sa.Column("median_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("median_price_per_m2", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_snapshots")),
    )
    op.create_index(
        "ux_market_snapshots_segment_day",
        "market_snapshots",
        ["day", "scope_key", "property_type_code", "purpose", "currency", "include_demo"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("market_snapshots")
