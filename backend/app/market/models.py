"""Daily market snapshots: what the platform's active listings looked like on a day.

Snapshots are recorded going forward only; history is never back-filled, so a
supply trend exists only once at least two days have been recorded.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MarketSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index(
            "ux_market_snapshots_segment_day",
            "day",
            "scope_key",
            "property_type_code",
            "purpose",
            "currency",
            "include_demo",
            unique=True,
        ),
    )

    day: Mapped[date] = mapped_column(Date, nullable=False)
    # "iraq", "governorate:<uuid>" or "city:<uuid>"
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    property_type_code: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    include_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active_listings: Mapped[int] = mapped_column(Integer, nullable=False)
    priced_listings: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    median_price_per_m2: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
