"""Monetization: plans, payments, subscriptions and listing promotions.

Payments go through a provider abstraction (``app.billing.providers``). The
default provider is DEMO: no money moves, every record is flagged ``is_demo``
and the UI says so. Prices are configuration made by administrators — none are
hard-coded; the DEMO seed creates clearly labelled example plans only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.properties.enums import sql_in


class PlanKind(StrEnum):
    SUBSCRIPTION = "SUBSCRIPTION"  # recurring entitlements (featured credits per period)
    PROMOTION = "PROMOTION"  # one-off: feature one listing for N days


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    REFUNDED = "REFUNDED"


class SubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_plans"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(PlanKind)})", name="kind_valid"),
        CheckConstraint("currency IN ('IQD','USD')", name="currency_valid"),
        CheckConstraint("price_amount >= 0", name="price_non_negative"),
        CheckConstraint("duration_days BETWEEN 1 AND 366", name="duration_range"),
        CheckConstraint("featured_credits >= 0", name="credits_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Subscription period, or how long a promotion keeps a listing featured.
    duration_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    featured_credits: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_payments"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(PaymentStatus)})", name="status_valid"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        Index(
            "uq_billing_payments_provider_ref",
            "provider",
            "provider_ref",
            unique=True,
            postgresql_where=text("provider_ref IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(SubscriptionStatus)})", name="status_valid"),
        CheckConstraint("credits_remaining >= 0", name="credits_non_negative"),
        # One live subscription per user.
        Index(
            "uq_billing_subscriptions_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    credits_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_payments.id", ondelete="SET NULL")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Promotion(UUIDPrimaryKeyMixin, Base):
    """One period during which a listing is featured (shown with a 'promoted' label)."""

    __tablename__ = "billing_promotions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="period_valid"),
        CheckConstraint("payment_id IS NOT NULL OR subscription_id IS NOT NULL", name="has_source"),
        Index("ix_billing_promotions_property_ends", "property_id", "ends_at"),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_payments.id", ondelete="SET NULL")
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_subscriptions.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
