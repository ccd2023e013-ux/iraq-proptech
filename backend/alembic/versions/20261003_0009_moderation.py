"""Moderation: reports, error events, moderation reason codes.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("status_reason_code", sa.String(24), nullable=True))
    op.add_column("property_status_history", sa.Column("reason_code", sa.String(24), nullable=True))

    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("reporter_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("assigned_to_id", sa.UUID(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "target_type IN ('PROPERTY','USER','AGENCY')", name=op.f("ck_reports_target_valid")
        ),
        sa.CheckConstraint(
            "reason IN ('FAKE','DUPLICATE','INCORRECT','INAPPROPRIATE','SCAM','SPAM','OTHER')",
            name=op.f("ck_reports_reason_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')",
            name=op.f("ck_reports_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            name=op.f("fk_reports_reporter_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_id"],
            ["users.id"],
            name=op.f("fk_reports_assigned_to_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_id"],
            ["users.id"],
            name=op.f("fk_reports_resolved_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index("ix_reports_status_created", "reports", ["status", "created_at"])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])
    op.create_index(
        "uq_reports_open_per_reporter",
        "reports",
        ["reporter_id", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN','IN_REVIEW')"),
    )

    op.create_table(
        "error_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("path", sa.String(300), nullable=True),
        sa.Column("error_type", sa.String(120), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_error_events")),
    )
    op.create_index("ix_error_events_created", "error_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("error_events")
    op.drop_table("reports")
    op.drop_column("property_status_history", "reason_code")
    op.drop_column("properties", "status_reason_code")
