"""Trust & safety: user reports and operational error records."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReportTarget(StrEnum):
    PROPERTY = "PROPERTY"
    USER = "USER"
    AGENCY = "AGENCY"


class ReportReason(StrEnum):
    FAKE = "FAKE"
    DUPLICATE = "DUPLICATE"
    INCORRECT = "INCORRECT"
    INAPPROPRIATE = "INAPPROPRIATE"
    SCAM = "SCAM"
    SPAM = "SPAM"
    OTHER = "OTHER"


class ReportStatus(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


def _in(enum: type[StrEnum]) -> str:
    return ",".join(f"'{e.value}'" for e in enum)


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(f"target_type IN ({_in(ReportTarget)})", name="target_valid"),
        CheckConstraint(f"reason IN ({_in(ReportReason)})", name="reason_valid"),
        CheckConstraint(f"status IN ({_in(ReportStatus)})", name="status_valid"),
        Index("ix_reports_status_created", "status", "created_at"),
        Index("ix_reports_target", "target_type", "target_id"),
        # One open report per reporter per target (no report spamming).
        Index(
            "uq_reports_open_per_reporter",
            "reporter_id",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN','IN_REVIEW')"),
        ),
    )

    target_type: Mapped[str] = mapped_column(String(10), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=ReportStatus.OPEN)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ErrorEvent(UUIDPrimaryKeyMixin, Base):
    """Unhandled server errors (no request bodies or personal data stored)."""

    __tablename__ = "error_events"
    __table_args__ = (Index("ix_error_events_created", "created_at"),)

    request_id: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(300))
    error_type: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
