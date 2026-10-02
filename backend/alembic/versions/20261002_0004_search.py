"""Search: Arabic normalization, full-text and trigram indexes, favorites.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02

``normalize_ar`` folds Arabic spelling variants so "أربيل"/"اربيل",
"البصرة"/"البصره" and Arabic-Indic digits match. It is IMMUTABLE so it can
feed generated columns and indexes. Plain SQL — portable to any PostgreSQL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_TEXT_SQL = (
    "normalize_ar(coalesce(title_ar, '') || ' ' || coalesce(title_en, '') || ' ' || "
    "coalesce(description_ar, '') || ' ' || coalesce(description_en, '') || ' ' || "
    "coalesce(street, '') || ' ' || coalesce(address_text, '') || ' ' || reference_code)"
)

NORMALIZE_AR = r"""
CREATE OR REPLACE FUNCTION normalize_ar(input text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT lower(
    regexp_replace(
      translate(coalesce(input, ''), 'أإآٱىة٠١٢٣٤٥٦٧٨٩ـ', 'اااايه0123456789'),
      '[ً-ْٰ]', '', 'g'
    )
  )
$$;
"""


def upgrade() -> None:
    op.execute(NORMALIZE_AR)
    op.add_column(
        "properties",
        sa.Column(
            "search_text", sa.Text(), sa.Computed(SEARCH_TEXT_SQL, persisted=True), nullable=True
        ),
    )
    op.add_column(
        "properties",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(f"to_tsvector('simple', {SEARCH_TEXT_SQL})", persisted=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_properties_search_vector", "properties", ["search_vector"], postgresql_using="gin"
    )
    op.create_index(
        "ix_properties_search_text_trgm",
        "properties",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_properties_status_price", "properties", ["status", "currency", "price_amount"]
    )
    op.create_index("ix_properties_status_area", "properties", ["status", "area_m2"])

    op.create_table(
        "favorites",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_favorites_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_favorites_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "property_id", name=op.f("pk_favorites")),
    )
    op.create_index(op.f("ix_favorites_property_id"), "favorites", ["property_id"])


def downgrade() -> None:
    op.drop_table("favorites")
    op.drop_index("ix_properties_status_area", table_name="properties")
    op.drop_index("ix_properties_status_price", table_name="properties")
    op.drop_index("ix_properties_search_text_trgm", table_name="properties")
    op.drop_index("ix_properties_search_vector", table_name="properties")
    op.drop_column("properties", "search_vector")
    op.drop_column("properties", "search_text")
    op.execute("DROP FUNCTION IF EXISTS normalize_ar(text)")
