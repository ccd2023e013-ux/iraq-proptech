"""Notifications, delivery outbox, push subscriptions, webhooks, job runs.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = "status IN ('PENDING','SENT','FAILED','SKIPPED')"


def _id() -> sa.Column:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [target],
        name=op.f(f"fk_{table}_{column}_{target.split('.')[0]}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    t = "notifications"
    op.create_table(
        t,
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title_ar", sa.String(200), nullable=False),
        sa.Column("title_en", sa.String(200), nullable=False),
        sa.Column("body_ar", sa.Text(), nullable=True),
        sa.Column("body_en", sa.Text(), nullable=True),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("data", _jsonb(), nullable=True),
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _fk(t, "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index("ix_notifications_user_created", t, ["user_id", "created_at"])
    op.create_index(
        "uq_notifications_dedupe",
        t,
        ["user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )

    t = "notification_preferences"
    op.create_table(
        t,
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False),
        sa.Column("push_enabled", sa.Boolean(), nullable=False),
        sa.Column("categories", _jsonb(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _fk(t, "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f(f"pk_{t}")),
    )

    t = "notification_deliveries"
    op.create_table(
        t,
        _id(),
        sa.Column("notification_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("subject", sa.String(200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(300), nullable=True),
        _ts("next_attempt_at"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        sa.CheckConstraint("channel IN ('EMAIL','SMS','PUSH')", name=op.f(f"ck_{t}_channel_valid")),
        sa.CheckConstraint(STATUSES, name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "notification_id", "notifications.id", "CASCADE"),
        _fk(t, "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_notification_id"), t, ["notification_id"])
    op.create_index("ix_notification_deliveries_status_next", t, ["status", "next_attempt_at"])

    t = "push_subscriptions"
    op.create_table(
        t,
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(100), nullable=False),
        _ts("created_at"),
        _fk(t, "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_user_id"), t, ["user_id"])
    op.create_index("uq_push_subscriptions_endpoint", t, ["endpoint"], unique=True)

    t = "webhook_endpoints"
    op.create_table(
        t,
        _id(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("secret", sa.String(100), nullable=False),
        sa.Column("events", _jsonb(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_status", sa.Integer(), nullable=True),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        _fk(t, "created_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )

    t = "webhook_deliveries"
    op.create_table(
        t,
        _id(),
        sa.Column("endpoint_id", sa.UUID(), nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("payload", _jsonb(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
        _ts("next_attempt_at"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        sa.CheckConstraint(STATUSES, name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "endpoint_id", "webhook_endpoints.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index(op.f(f"ix_{t}_endpoint_id"), t, ["endpoint_id"])
    op.create_index("ix_webhook_deliveries_status_next", t, ["status", "next_attempt_at"])

    t = "job_runs"
    op.create_table(
        t,
        _id(),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("detail", _jsonb(), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
        _ts("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')", name=op.f(f"ck_{t}_status_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    op.create_index("ix_job_runs_name_started", t, ["name", "started_at"])


def downgrade() -> None:
    for table in (
        "job_runs",
        "webhook_deliveries",
        "webhook_endpoints",
        "push_subscriptions",
        "notification_deliveries",
        "notification_preferences",
        "notifications",
    ):
        op.drop_table(table)
