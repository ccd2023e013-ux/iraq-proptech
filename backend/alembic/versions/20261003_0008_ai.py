"""AI generations (traceability and usage).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_generations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("feature", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED','REJECTED','FAILED','FALLBACK')",
            name=op.f("ck_ai_generations_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_ai_generations_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"],
            name=op.f("fk_ai_generations_property_id_properties"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["crm_leads.id"], name=op.f("fk_ai_generations_lead_id_crm_leads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_generations")),
    )
    op.create_index(op.f("ix_ai_generations_property_id"), "ai_generations", ["property_id"])
    op.create_index(
        "ix_ai_generations_feature_created", "ai_generations", ["feature", "created_at"]
    )
    op.create_index("ix_ai_generations_user_created", "ai_generations", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ai_generations")
