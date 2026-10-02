"""CRM: lead statuses, customers, leads, activities, inquiries, tasks, appointments.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEAD_SOURCES = "'INQUIRY','MANUAL','PHONE','WHATSAPP','WALK_IN','REFERRAL','SOCIAL','OTHER'"
PRIORITIES = "'LOW','NORMAL','HIGH'"
KINDS = (
    "'NOTE','CALL','WHATSAPP','EMAIL','SMS','MEETING','INQUIRY','STATUS_CHANGE',"
    "'ASSIGNMENT','TASK','APPOINTMENT'"
)

# (code, ar, en, terminal, won)
STATUSES = [
    ("NEW", "جديد", "New", False, False),
    ("CONTACTED", "تم التواصل", "Contacted", False, False),
    ("QUALIFIED", "مؤهّل", "Qualified", False, False),
    ("VIEWING", "معاينة", "Viewing", False, False),
    ("NEGOTIATION", "تفاوض", "Negotiation", False, False),
    ("WON", "تمت الصفقة", "Won", True, True),
    ("LOST", "خسارة", "Lost", True, False),
]


def _id() -> sa.Column:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    ref_table = target.split(".")[0]
    return sa.ForeignKeyConstraint(
        [column], [target], name=op.f(f"fk_{table}_{column}_{ref_table}"), ondelete=ondelete
    )


def upgrade() -> None:
    statuses = op.create_table(
        "lead_statuses",
        sa.Column("code", sa.String(24), nullable=False),
        sa.Column("name_ar", sa.String(80), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False),
        sa.Column("is_won", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_lead_statuses")),
    )
    op.bulk_insert(
        statuses,
        [
            {
                "code": code,
                "name_ar": ar,
                "name_en": en,
                "sort_order": i * 10,
                "is_terminal": terminal,
                "is_won": won,
                "is_active": True,
                "is_system": True,
            }
            for i, (code, ar, en, terminal, won) in enumerate(STATUSES)
        ],
    )

    t = "crm_customers"
    op.create_table(
        t,
        _id(),
        sa.Column("agency_id", sa.UUID(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "agency_id IS NOT NULL OR owner_user_id IS NOT NULL", name=op.f(f"ck_{t}_has_scope")
        ),
        _fk(t, "agency_id", "agencies.id", "CASCADE"),
        _fk(t, "owner_user_id", "users.id", "CASCADE"),
        _fk(t, "user_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_agency_id"), t, ["agency_id"])
    op.create_index(op.f(f"ix_{t}_owner_user_id"), t, ["owner_user_id"])
    op.create_index(
        "uq_crm_customers_agency_user",
        t,
        ["agency_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("agency_id IS NOT NULL AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_crm_customers_owner_user",
        t,
        ["owner_user_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("agency_id IS NULL AND user_id IS NOT NULL"),
    )

    t = "crm_leads"
    op.create_table(
        t,
        _id(),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("agency_id", sa.UUID(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("assigned_to_id", sa.UUID(), nullable=True),
        sa.Column("status_code", sa.String(24), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("budget_min", sa.Numeric(18, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(18, 2), nullable=True),
        sa.Column("budget_currency", sa.String(3), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(f"source IN ({LEAD_SOURCES})", name=op.f(f"ck_{t}_source_valid")),
        sa.CheckConstraint(f"priority IN ({PRIORITIES})", name=op.f(f"ck_{t}_priority_valid")),
        sa.CheckConstraint(
            "budget_currency IS NULL OR budget_currency IN ('IQD','USD')",
            name=op.f(f"ck_{t}_currency_valid"),
        ),
        sa.CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name=op.f(f"ck_{t}_budget_range"),
        ),
        _fk(t, "customer_id", "crm_customers.id", "CASCADE"),
        _fk(t, "property_id", "properties.id", "SET NULL"),
        _fk(t, "agency_id", "agencies.id", "CASCADE"),
        _fk(t, "owner_user_id", "users.id", "RESTRICT"),
        _fk(t, "assigned_to_id", "users.id", "SET NULL"),
        _fk(t, "status_code", "lead_statuses.code", "RESTRICT"),
        _fk(t, "created_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    for col in ("customer_id", "property_id", "assigned_to_id", "status_code", "next_follow_up_at"):
        op.create_index(op.f(f"ix_{t}_{col}"), t, [col])
    op.create_index("ix_crm_leads_agency_status", t, ["agency_id", "status_code"])
    op.create_index("ix_crm_leads_owner_status", t, ["owner_user_id", "status_code"])

    t = "crm_lead_activities"
    op.create_table(
        t,
        _id(),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _ts("occurred_at"),
        _ts("created_at"),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f(f"ck_{t}_kind_valid")),
        _fk(t, "lead_id", "crm_leads.id", "CASCADE"),
        _fk(t, "actor_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index("ix_crm_lead_activities_lead_occurred", t, ["lead_id", "occurred_at"])

    t = "inquiries"
    op.create_table(
        t,
        _id(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("preferred_contact", sa.String(10), nullable=False),
        _ts("created_at"),
        sa.CheckConstraint(
            "preferred_contact IN ('PHONE','WHATSAPP','EMAIL','ANY')",
            name=op.f(f"ck_{t}_preferred_contact_valid"),
        ),
        _fk(t, "property_id", "properties.id", "CASCADE"),
        _fk(t, "sender_id", "users.id", "SET NULL"),
        _fk(t, "lead_id", "crm_leads.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    for col in ("property_id", "sender_id", "lead_id"):
        op.create_index(op.f(f"ix_{t}_{col}"), t, [col])

    t = "crm_tasks"
    op.create_table(
        t,
        _id(),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("agency_id", sa.UUID(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("assigned_to_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(8), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(f"priority IN ({PRIORITIES})", name=op.f(f"ck_{t}_priority_valid")),
        sa.CheckConstraint(
            "agency_id IS NOT NULL OR owner_user_id IS NOT NULL", name=op.f(f"ck_{t}_has_scope")
        ),
        _fk(t, "lead_id", "crm_leads.id", "CASCADE"),
        _fk(t, "agency_id", "agencies.id", "CASCADE"),
        _fk(t, "owner_user_id", "users.id", "CASCADE"),
        _fk(t, "assigned_to_id", "users.id", "SET NULL"),
        _fk(t, "created_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    for col in ("lead_id", "agency_id", "assigned_to_id", "due_at"):
        op.create_index(op.f(f"ix_{t}_{col}"), t, [col])

    t = "crm_appointments"
    op.create_table(
        t,
        _id(),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("organizer_id", sa.UUID(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location_text", sa.String(300), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "status IN ('SCHEDULED','COMPLETED','CANCELLED','NO_SHOW')",
            name=op.f(f"ck_{t}_status_valid"),
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name=op.f(f"ck_{t}_time_order")
        ),
        _fk(t, "lead_id", "crm_leads.id", "CASCADE"),
        _fk(t, "property_id", "properties.id", "SET NULL"),
        _fk(t, "organizer_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    for col in ("lead_id", "starts_at"):
        op.create_index(op.f(f"ix_{t}_{col}"), t, [col])


def downgrade() -> None:
    for table in (
        "crm_appointments",
        "crm_tasks",
        "inquiries",
        "crm_lead_activities",
        "crm_leads",
        "crm_customers",
        "lead_statuses",
    ):
        op.drop_table(table)
