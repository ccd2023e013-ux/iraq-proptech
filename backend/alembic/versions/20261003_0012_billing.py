"""Billing: plans, payments, subscriptions, promotions; properties.featured_until.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [target],
        name=op.f(f"fk_{table}_{column}_{target.split('.')[0]}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.add_column(
        "properties", sa.Column("featured_until", sa.DateTime(timezone=True), nullable=True)
    )

    t = "billing_plans"
    op.create_table(
        t,
        _id(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("name_ar", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("duration_days", sa.SmallInteger(), nullable=False),
        sa.Column("featured_credits", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("kind IN ('SUBSCRIPTION','PROMOTION')", name=op.f(f"ck_{t}_kind_valid")),
        sa.CheckConstraint("currency IN ('IQD','USD')", name=op.f(f"ck_{t}_currency_valid")),
        sa.CheckConstraint("price_amount >= 0", name=op.f(f"ck_{t}_price_non_negative")),
        sa.CheckConstraint("duration_days BETWEEN 1 AND 366", name=op.f(f"ck_{t}_duration_range")),
        sa.CheckConstraint("featured_credits >= 0", name=op.f(f"ck_{t}_credits_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
        sa.UniqueConstraint("code", name=op.f(f"uq_{t}_code")),
    )

    t = "billing_payments"
    op.create_table(
        t,
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_ref", sa.String(120), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(200), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "status IN ('PENDING','SUCCEEDED','FAILED','CANCELED','REFUNDED')",
            name=op.f(f"ck_{t}_status_valid"),
        ),
        sa.CheckConstraint("amount >= 0", name=op.f(f"ck_{t}_amount_non_negative")),
        _fk(t, "user_id", "users.id", "RESTRICT"),
        _fk(t, "plan_id", "billing_plans.id", "RESTRICT"),
        _fk(t, "property_id", "properties.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_user_id"), t, ["user_id"])
    op.create_index(
        "uq_billing_payments_provider_ref",
        t,
        ["provider", "provider_ref"],
        unique=True,
        postgresql_where=sa.text("provider_ref IS NOT NULL"),
    )

    t = "billing_subscriptions"
    op.create_table(
        t,
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("credits_remaining", sa.Integer(), nullable=False),
        sa.Column("last_payment_id", sa.UUID(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','CANCELED','EXPIRED')", name=op.f(f"ck_{t}_status_valid")
        ),
        sa.CheckConstraint("credits_remaining >= 0", name=op.f(f"ck_{t}_credits_non_negative")),
        _fk(t, "user_id", "users.id", "CASCADE"),
        _fk(t, "plan_id", "billing_plans.id", "RESTRICT"),
        _fk(t, "last_payment_id", "billing_payments.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_user_id"), t, ["user_id"])
    op.create_index(
        "uq_billing_subscriptions_active_user",
        t,
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    t = "billing_promotions"
    op.create_table(
        t,
        _id(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=True),
        sa.Column("subscription_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        _ts("created_at"),
        sa.CheckConstraint("ends_at > starts_at", name=op.f(f"ck_{t}_period_valid")),
        sa.CheckConstraint(
            "payment_id IS NOT NULL OR subscription_id IS NOT NULL",
            name=op.f(f"ck_{t}_has_source"),
        ),
        _fk(t, "property_id", "properties.id", "CASCADE"),
        _fk(t, "payment_id", "billing_payments.id", "SET NULL"),
        _fk(t, "subscription_id", "billing_subscriptions.id", "SET NULL"),
        _fk(t, "created_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index("ix_billing_promotions_property_ends", t, ["property_id", "ends_at"])


def downgrade() -> None:
    op.drop_table("billing_promotions")
    op.drop_table("billing_subscriptions")
    op.drop_table("billing_payments")
    op.drop_table("billing_plans")
    op.drop_column("properties", "featured_until")
