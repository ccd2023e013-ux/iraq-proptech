"""Privacy-conscious analytics: daily aggregates only.

No raw event stream with personal data is stored. A listing "view" is one
unique visitor per listing per local day. De-duplication uses a salted,
per-day hash of the visitor key (user id, or IP + user agent for anonymous
visitors) kept only for a short retention window, after which it is purged;
the daily salt is derived from the server secret so hashes cannot be linked
across days.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyViewDaily(Base):
    __tablename__ = "property_view_daily"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PropertyViewVisitor(Base):
    """Short-lived de-duplication keys (purged after ``VISITOR_RETENTION_DAYS``)."""

    __tablename__ = "property_view_visitors"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
    visitor_hash: Mapped[str] = mapped_column(String(64), primary_key=True)


class SearchStatDaily(Base):
    """Searches per day by governorate and purpose ('' = not specified). No query text."""

    __tablename__ = "search_stats_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    governorate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(12), primary_key=True)
    searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zero_results: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
