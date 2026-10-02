"""Index every foreign key (found by tests/test_schema_audit.py).

Unindexed foreign keys make joins and filters on them sequential scans, and
make deletes/updates on the referenced row scan the child table under lock.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOREIGN_KEY_COLUMNS: list[tuple[str, str]] = [
    ("agencies", "created_by_id"),
    ("agencies", "verified_by_id"),
    ("agency_invitations", "agency_id"),
    ("agency_invitations", "invited_by_id"),
    ("ai_generations", "lead_id"),
    ("billing_payments", "plan_id"),
    ("billing_payments", "property_id"),
    ("billing_promotions", "created_by_id"),
    ("billing_promotions", "payment_id"),
    ("billing_promotions", "subscription_id"),
    ("billing_subscriptions", "last_payment_id"),
    ("billing_subscriptions", "plan_id"),
    ("conversations", "property_id"),
    ("crm_appointments", "organizer_id"),
    ("crm_appointments", "property_id"),
    ("crm_customers", "user_id"),
    ("crm_lead_activities", "actor_id"),
    ("crm_leads", "created_by_id"),
    ("crm_tasks", "created_by_id"),
    ("crm_tasks", "owner_user_id"),
    ("exchange_rates", "created_by_id"),
    ("messages", "sender_id"),
    ("notification_deliveries", "user_id"),
    ("properties", "governorate_id"),
    ("properties", "property_type_code"),
    ("property_documents", "uploaded_by_id"),
    ("property_media", "uploaded_by_id"),
    ("property_price_history", "changed_by_id"),
    ("property_status_history", "changed_by_id"),
    ("property_verifications", "document_id"),
    ("property_verifications", "verified_by_id"),
    ("property_view_visitors", "property_id"),
    ("reports", "assigned_to_id"),
    ("reports", "resolved_by_id"),
    ("user_roles", "granted_by_id"),
    ("webhook_endpoints", "created_by_id"),
]


def upgrade() -> None:
    for table, column in FOREIGN_KEY_COLUMNS:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column])


def downgrade() -> None:
    for table, column in reversed(FOREIGN_KEY_COLUMNS):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
