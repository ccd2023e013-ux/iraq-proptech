"""Analytics: daily listing views, short-lived visitor de-duplication, search stats.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _property_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["property_id"],
        ["properties.id"],
        name=op.f(f"fk_{table}_property_id_properties"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    t = "property_view_daily"
    op.create_table(
        t,
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        _property_fk(t),
        sa.PrimaryKeyConstraint("property_id", "day", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_day"), t, ["day"])

    t = "property_view_visitors"
    op.create_table(
        t,
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("visitor_hash", sa.String(64), nullable=False),
        _property_fk(t),
        sa.PrimaryKeyConstraint("day", "property_id", "visitor_hash", name=op.f(f"pk_{t}")),
    )

    t = "search_stats_daily"
    op.create_table(
        t,
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("governorate_id", sa.String(36), nullable=False),
        sa.Column("purpose", sa.String(12), nullable=False),
        sa.Column("searches", sa.Integer(), nullable=False),
        sa.Column("zero_results", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "governorate_id", "purpose", name=op.f(f"pk_{t}")),
    )


def downgrade() -> None:
    op.drop_table("search_stats_daily")
    op.drop_table("property_view_visitors")
    op.drop_table("property_view_daily")
