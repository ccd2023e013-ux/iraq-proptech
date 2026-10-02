"""Authentication, RBAC and audit log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the role catalog at this revision (migrations must not import
# app code that may change later). Later revisions add/alter rows explicitly.
ROLES = [
    ("SUPER_ADMIN", "مدير النظام الأعلى", "Super administrator", 100),
    ("ADMIN", "مدير", "Administrator", 90),
    ("MODERATOR", "مشرف محتوى", "Moderator", 70),
    ("AGENCY_OWNER", "صاحب مكتب عقاري", "Agency owner", 50),
    ("AGENT", "وكيل عقاري", "Agent", 40),
    ("PROPERTY_OWNER", "مالك عقار", "Property owner", 20),
    ("CUSTOMER", "عميل", "Customer", 10),
]


def _ts(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now() if default else None,
        nullable=nullable,
    )


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("rank BETWEEN 0 AND 100", name=op.f("ck_roles_rank_range")),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_roles")),
    )
    op.bulk_insert(
        roles,
        [{"code": c, "name_ar": ar, "name_en": en, "rank": r} for c, ar, en, r in ROLES],
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("preferred_locale", sa.String(5), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        _ts("email_verified_at", nullable=True, default=False),
        _ts("phone_verified_at", nullable=True, default=False),
        _ts("last_login_at", nullable=True, default=False),
        _ts("password_changed_at", nullable=True, default=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("deleted_at", nullable=True, default=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','DEACTIVATED')", name=op.f("ck_users_status_valid")
        ),
        sa.CheckConstraint("preferred_locale IN ('ar','en')", name=op.f("ck_users_locale_valid")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("phone", name=op.f("uq_users_phone")),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_code", sa.String(32), nullable=False),
        sa.Column("granted_by_id", sa.UUID(), nullable=True),
        _ts("granted_at"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_code"],
            ["roles.code"],
            name=op.f("fk_user_roles_role_code_roles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_id"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_code", name=op.f("pk_user_roles")),
    )
    op.create_index(op.f("ix_user_roles_role_code"), "user_roles", ["role_code"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        _ts("created_at"),
        _ts("last_used_at"),
        _ts("expires_at", default=False),
        _ts("revoked_at", nullable=True, default=False),
        sa.Column("revoke_reason", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        _ts("created_at"),
        _ts("expires_at", default=False),
        _ts("used_at", nullable=True, default=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            name=op.f("fk_refresh_tokens_session_id_auth_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_session_id"), "refresh_tokens", ["session_id"])

    op.create_table(
        "verification_tokens",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("target", sa.String(320), nullable=False),
        _ts("created_at"),
        _ts("expires_at", default=False),
        _ts("consumed_at", nullable=True, default=False),
        sa.CheckConstraint(
            "purpose IN ('EMAIL_VERIFY','PHONE_VERIFY','PASSWORD_RESET')",
            name=op.f("ck_verification_tokens_purpose_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_verification_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_verification_tokens_token_hash")),
    )
    op.create_index(
        "ix_verification_tokens_user_purpose", "verification_tokens", ["user_id", "purpose"]
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        _ts("occurred_at"),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_occurred_at"), "audit_logs", ["occurred_at"])
    op.create_index(op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"])
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("verification_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("auth_sessions")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
