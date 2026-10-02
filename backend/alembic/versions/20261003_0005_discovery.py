"""Discovery: saved searches, points of interest, exchange rates.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POI_CATEGORIES = (
    "'SCHOOL','UNIVERSITY','HOSPITAL','CLINIC','PHARMACY','MOSQUE','CHURCH','MARKET','MALL',"
    "'PARK','GOVERNMENT','BANK','FUEL','TRANSPORT','RESTAURANT','OTHER'"
)


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _id() -> sa.Column:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alert_frequency", sa.String(8), nullable=False),
        sa.Column("last_alerted_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "alert_frequency IN ('NONE','INSTANT','DAILY','WEEKLY')",
            name=op.f("ck_saved_searches_frequency_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_saved_searches_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_searches")),
    )
    op.create_index(op.f("ix_saved_searches_user_id"), "saved_searches", ["user_id"])

    op.create_table(
        "points_of_interest",
        _id(),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("city_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("external_ref", sa.String(120), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            f"category IN ({POI_CATEGORIES})", name=op.f("ck_points_of_interest_category_valid")
        ),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_points_of_interest_city_id_cities"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_points_of_interest")),
    )
    op.create_index(op.f("ix_points_of_interest_category"), "points_of_interest", ["category"])
    op.create_index(op.f("ix_points_of_interest_city_id"), "points_of_interest", ["city_id"])
    op.create_index(
        "ix_points_of_interest_location",
        "points_of_interest",
        ["location"],
        postgresql_using="gist",
    )

    op.create_table(
        "exchange_rates",
        _id(),
        sa.Column("base", sa.String(3), nullable=False),
        sa.Column("quote", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "base IN ('IQD','USD') AND quote IN ('IQD','USD')",
            name=op.f("ck_exchange_rates_currency_valid"),
        ),
        sa.CheckConstraint("base <> quote", name=op.f("ck_exchange_rates_distinct_pair")),
        sa.CheckConstraint("rate > 0", name=op.f("ck_exchange_rates_rate_positive")),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_exchange_rates_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exchange_rates")),
    )
    op.create_index(
        "ix_exchange_rates_pair_effective", "exchange_rates", ["base", "quote", "effective_at"]
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
    op.drop_table("points_of_interest")
    op.drop_table("saved_searches")
