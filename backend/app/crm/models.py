"""CRM: inquiries, customers, leads, pipeline statuses, activities, tasks, appointments.

Scope: every customer, lead and task belongs either to an **agency**
(`agency_id`) or, for independent listers, to a **user** (`owner_user_id`).
Authorization (`app/crm/policies.py`) is derived from that scope plus the
caller's permissions — never from IDs supplied by the client.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def sql_in(enum: type[StrEnum]) -> str:
    return ",".join(f"'{e.value}'" for e in enum)


class CoreStatus(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    VIEWING = "VIEWING"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class LeadSource(StrEnum):
    INQUIRY = "INQUIRY"
    MANUAL = "MANUAL"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    WALK_IN = "WALK_IN"
    REFERRAL = "REFERRAL"
    SOCIAL = "SOCIAL"
    OTHER = "OTHER"


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class ActivityKind(StrEnum):
    NOTE = "NOTE"
    CALL = "CALL"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    MEETING = "MEETING"
    INQUIRY = "INQUIRY"
    STATUS_CHANGE = "STATUS_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"
    TASK = "TASK"
    APPOINTMENT = "APPOINTMENT"


# Kinds a user may log by hand; the rest are written by the system.
MANUAL_ACTIVITY_KINDS = {
    ActivityKind.NOTE,
    ActivityKind.CALL,
    ActivityKind.WHATSAPP,
    ActivityKind.EMAIL,
    ActivityKind.SMS,
    ActivityKind.MEETING,
}


class ContactPreference(StrEnum):
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    ANY = "ANY"


class AppointmentStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class LeadStatus(Base):
    """Configurable pipeline stage. Core codes are seeded and cannot be removed."""

    __tablename__ = "lead_statuses"

    code: Mapped[str] = mapped_column(String(24), primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(80), nullable=False)
    name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_customers"
    __table_args__ = (
        CheckConstraint("agency_id IS NOT NULL OR owner_user_id IS NOT NULL", name="has_scope"),
        Index(
            "uq_crm_customers_agency_user",
            "agency_id",
            "user_id",
            unique=True,
            postgresql_where=text("agency_id IS NOT NULL AND user_id IS NOT NULL"),
        ),
        Index(
            "uq_crm_customers_owner_user",
            "owner_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("agency_id IS NULL AND user_id IS NOT NULL"),
        ),
    )

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(320))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=LeadSource.MANUAL)


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_leads"
    __table_args__ = (
        CheckConstraint(f"source IN ({sql_in(LeadSource)})", name="source_valid"),
        CheckConstraint(f"priority IN ({sql_in(Priority)})", name="priority_valid"),
        CheckConstraint(
            "budget_currency IS NULL OR budget_currency IN ('IQD','USD')", name="currency_valid"
        ),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="budget_range",
        ),
        Index("ix_crm_leads_agency_status", "agency_id", "status_code"),
        Index("ix_crm_leads_owner_status", "owner_user_id", "status_code"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crm_customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL"), index=True
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE")
    )
    # Accountable lister (agent or independent owner).
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status_code: Mapped[str] = mapped_column(
        String(24),
        ForeignKey("lead_statuses.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=LeadSource.MANUAL)
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default=Priority.NORMAL)
    budget_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_reason: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class LeadActivity(UUIDPrimaryKeyMixin, Base):
    """Timeline / contact history. Append-only."""

    __tablename__ = "crm_lead_activities"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(ActivityKind)})", name="kind_valid"),
        Index("ix_crm_lead_activities_lead_occurred", "lead_id", "occurred_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Inquiry(UUIDPrimaryKeyMixin, Base):
    """A message from a visitor about a listing (the raw input that creates a lead)."""

    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint(
            f"preferred_contact IN ({sql_in(ContactPreference)})", name="preferred_contact_valid"
        ),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_leads.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(320))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_contact: Mapped[str] = mapped_column(
        String(10), nullable=False, default=ContactPreference.ANY
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CrmTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_tasks"
    __table_args__ = (
        CheckConstraint(f"priority IN ({sql_in(Priority)})", name="priority_valid"),
        CheckConstraint("agency_id IS NOT NULL OR owner_user_id IS NOT NULL", name="has_scope"),
    )

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_leads.id", ondelete="CASCADE"), index=True
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default=Priority.NORMAL)


class Appointment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_appointments"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(AppointmentStatus)})", name="status_valid"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="time_order"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crm_leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL")
    )
    organizer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location_text: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default=AppointmentStatus.SCHEDULED
    )
    notes: Mapped[str | None] = mapped_column(Text)
