"""Notifications, delivery outbox, webhooks and background job records.

Reliable-outbox design: anything that leaves the system (email, SMS, push,
webhook) is first written as a PENDING row in the same transaction as the
change that caused it, then delivered by workers with retries. Nothing is lost
if a provider or the worker is down, and n8n/other automation is just one more
webhook consumer — never a dependency.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Channel(StrEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"  # gave up after retries
    SKIPPED = "SKIPPED"  # no address / channel disabled at send time


class Category(StrEnum):
    LEADS = "leads"
    MESSAGES = "messages"
    LISTINGS = "listings"
    SAVED_SEARCHES = "saved_searches"
    REPORTS = "reports"
    REMINDERS = "reminders"
    ACCOUNT = "account"


class Notification(UUIDPrimaryKeyMixin, Base):
    """In-app notification (always created; other channels follow preferences)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index(
            "uq_notifications_dedupe",
            "user_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    body_ar: Mapped[str | None] = mapped_column(Text)
    body_en: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # category -> enabled; missing categories are enabled
    categories: Mapped[dict[str, bool]] = mapped_column(JSONB, nullable=False, default=dict)


class NotificationDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("channel IN ('EMAIL','SMS','PUSH')", name="channel_valid"),
        CheckConstraint("status IN ('PENDING','SENT','FAILED','SKIPPED')", name="status_valid"),
        Index("ix_notification_deliveries_status_next", "status", "next_attempt_at"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(8), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default=DeliveryStatus.PENDING)
    provider: Mapped[str | None] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PushSubscription(UUIDPrimaryKeyMixin, Base):
    """Browser Web Push subscription (architecture; real sending needs VAPID keys)."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (Index("uq_push_subscriptions_endpoint", "endpoint", unique=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebhookEndpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Outgoing webhook subscription (n8n, Zapier-like tools, partner systems)."""

    __tablename__ = "webhook_endpoints"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Signing secret (HMAC-SHA256). Shown once at creation, never returned again.
    secret: Mapped[str] = mapped_column(String(100), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_status: Mapped[int | None] = mapped_column(Integer)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','SENT','FAILED','SKIPPED')", name="status_valid"),
        Index("ix_webhook_deliveries_status_next", "status", "next_attempt_at"),
    )

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default=DeliveryStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(String(300))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobRun(UUIDPrimaryKeyMixin, Base):
    """One execution of a scheduled/background job (for the admin jobs view)."""

    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint("status IN ('RUNNING','SUCCEEDED','FAILED')", name="status_valid"),
        Index("ix_job_runs_name_started", "name", "started_at"),
    )

    name: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(String(300))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
