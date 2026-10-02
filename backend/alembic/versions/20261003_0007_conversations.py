"""Conversations and messages; MESSAGE lead-activity kind.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = (
    "'NOTE','CALL','WHATSAPP','EMAIL','SMS','MEETING','INQUIRY','STATUS_CHANGE',"
    "'ASSIGNMENT','TASK','APPOINTMENT'"
)
NEW_KINDS = OLD_KINDS + ",'MESSAGE'"


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_crm_lead_activities_kind_valid"), "crm_lead_activities", type_="check")
    op.create_check_constraint(
        op.f("ck_crm_lead_activities_kind_valid"), "crm_lead_activities", f"kind IN ({NEW_KINDS})"
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("customer_user_id", sa.UUID(), nullable=False),
        sa.Column("lister_user_id", sa.UUID(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_conversations_property_id_properties"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["crm_leads.id"],
            name=op.f("fk_conversations_lead_id_crm_leads"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_user_id"],
            ["users.id"],
            name=op.f("fk_conversations_customer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lister_user_id"],
            ["users.id"],
            name=op.f("fk_conversations_lister_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    for col in ("lead_id", "customer_user_id", "lister_user_id"):
        op.create_index(op.f(f"ix_conversations_{col}"), "conversations", [col])
    op.create_index(
        "uq_conversations_customer_property",
        "conversations",
        ["customer_user_id", "property_id"],
        unique=True,
        postgresql_where=sa.text("property_id IS NOT NULL"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        _ts("created_at"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_messages_sender_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DELETE FROM crm_lead_activities WHERE kind = 'MESSAGE'")
    op.drop_constraint(op.f("ck_crm_lead_activities_kind_valid"), "crm_lead_activities", type_="check")
    op.create_check_constraint(
        op.f("ck_crm_lead_activities_kind_valid"), "crm_lead_activities", f"kind IN ({OLD_KINDS})"
    )
