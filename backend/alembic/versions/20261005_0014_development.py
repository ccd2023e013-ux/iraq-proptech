"""Development Intelligence: sources, projects and evidence (provenance).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_KINDS = "'OFFICIAL','PUBLIC','MEDIA','DEMO'"
CATEGORIES = (
    "'PORT','ROAD','BRIDGE_TUNNEL','RAIL','AIRPORT','WATER','POWER','HOUSING',"
    "'INDUSTRIAL','COMMERCIAL','PUBLIC_FACILITY','INVESTMENT_OPPORTUNITY'"
)
STATUSES = (
    "'OPPORTUNITY','PLANNED','TENDERED','UNDER_CONSTRUCTION','TRIAL_OPERATION',"
    "'COMPLETED','ON_HOLD','UNKNOWN'"
)
PRECISIONS = "'EXACT','APPROXIMATE','AREA'"
CONFIDENCES = "'HIGH','MEDIUM','LOW'"
SUPPORTS = "'EXISTENCE','STATUS','TIMELINE','LOCATION','FIGURES'"


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _id() -> sa.Column:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "development_sources",
        _id(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("organization", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("terms_note", sa.String(500), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            f"kind IN ({SOURCE_KINDS})", name=op.f("ck_development_sources_kind_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_development_sources")),
        sa.UniqueConstraint("url", name=op.f("uq_development_sources_url")),
    )

    op.create_table(
        "development_projects",
        _id(),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name_ar", sa.String(300), nullable=False),
        sa.Column("name_en", sa.String(300), nullable=True),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("summary_ar", sa.Text(), nullable=False),
        sa.Column("summary_en", sa.Text(), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("location_precision", sa.String(16), nullable=False),
        sa.Column("location_note", sa.String(300), nullable=True),
        sa.Column("governorate_id", sa.UUID(), nullable=True),
        sa.Column("timeline_ar", sa.String(300), nullable=True),
        sa.Column("timeline_en", sa.String(300), nullable=True),
        sa.Column("target_year", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(8), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            f"category IN ({CATEGORIES})", name=op.f("ck_development_projects_category_valid")
        ),
        sa.CheckConstraint(
            f"status IN ({STATUSES})", name=op.f("ck_development_projects_status_valid")
        ),
        sa.CheckConstraint(
            f"location_precision IN ({PRECISIONS})",
            name=op.f("ck_development_projects_precision_valid"),
        ),
        sa.CheckConstraint(
            f"confidence IN ({CONFIDENCES})", name=op.f("ck_development_projects_confidence_valid")
        ),
        sa.ForeignKeyConstraint(
            ["governorate_id"],
            ["governorates.id"],
            name=op.f("fk_development_projects_governorate_id_governorates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_development_projects_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_development_projects")),
        sa.UniqueConstraint("slug", name=op.f("uq_development_projects_slug")),
    )
    op.create_index(op.f("ix_development_projects_category"), "development_projects", ["category"])
    op.create_index(op.f("ix_development_projects_status"), "development_projects", ["status"])
    op.create_index(
        op.f("ix_development_projects_governorate_id"), "development_projects", ["governorate_id"]
    )
    op.create_index(
        op.f("ix_development_projects_created_by_id"), "development_projects", ["created_by_id"]
    )
    op.create_index(
        "ix_development_projects_location",
        "development_projects",
        ["location"],
        postgresql_using="gist",
    )

    op.create_table(
        "development_evidence",
        _id(),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excerpt", sa.String(600), nullable=True),
        sa.Column("supports", sa.String(16), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            f"supports IN ({SUPPORTS})", name=op.f("ck_development_evidence_supports_valid")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["development_projects.id"],
            name=op.f("fk_development_evidence_project_id_development_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["development_sources.id"],
            name=op.f("fk_development_evidence_source_id_development_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_development_evidence")),
    )
    op.create_index(
        op.f("ix_development_evidence_project_id"), "development_evidence", ["project_id"]
    )
    op.create_index(
        op.f("ix_development_evidence_source_id"), "development_evidence", ["source_id"]
    )


def downgrade() -> None:
    op.drop_table("development_evidence")
    op.drop_index("ix_development_projects_location", table_name="development_projects")
    op.drop_table("development_projects")
    op.drop_table("development_sources")
