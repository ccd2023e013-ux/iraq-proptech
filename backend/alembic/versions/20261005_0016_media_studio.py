"""Property Media Studio: render jobs.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_jobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("renderer", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("storyboard", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_key", sa.String(255), nullable=True),
        sa.Column("output_type", sa.String(40), nullable=True),
        sa.Column("output_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "renderer IN ('BROWSER','SERVER','EXTERNAL')",
            name=op.f("ck_media_jobs_renderer_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('STORYBOARD_READY','RENDERING','DONE','FAILED')",
            name=op.f("ck_media_jobs_status_valid"),
        ),
        sa.CheckConstraint(
            "format IN ('landscape','vertical')", name=op.f("ck_media_jobs_format_valid")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_media_jobs_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_media_jobs_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_jobs")),
    )
    op.create_index(op.f("ix_media_jobs_user_id"), "media_jobs", ["user_id"])
    op.create_index(op.f("ix_media_jobs_property_id"), "media_jobs", ["property_id"])


def downgrade() -> None:
    op.drop_table("media_jobs")
