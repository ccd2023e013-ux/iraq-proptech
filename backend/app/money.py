"""Currencies and exchange rates.

Listings keep their original currency (IQD or USD) and are **never**
converted for filtering, sorting or storage. Exchange rates exist only to show
an *indicative* equivalent, always labelled with the rate's source and date.
Rates are data entered by an operator (or a future provider adapter) — no
rate is hard-coded anywhere.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.audit import service as audit
from app.auth.deps import Principal, require_permission
from app.core.errors import AppError
from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.session import get_db
from app.rbac.catalog import Permission

Currency = Literal["IQD", "USD"]


class ExchangeRate(UUIDPrimaryKeyMixin, Base):
    """1 ``base`` = ``rate`` ``quote`` from ``effective_at`` (append-only history)."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        CheckConstraint("base IN ('IQD','USD') AND quote IN ('IQD','USD')", name="currency_valid"),
        CheckConstraint("base <> quote", name="distinct_pair"),
        CheckConstraint("rate > 0", name="rate_positive"),
        Index("ix_exchange_rates_pair_effective", "base", "quote", "effective_at"),
    )

    base: Mapped[str] = mapped_column(String(3), nullable=False)
    quote: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class RateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Currency = "USD"
    quote: Currency = "IQD"
    rate: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    source: str = Field(min_length=3, max_length=200)
    effective_at: datetime | None = None


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base: str
    quote: str
    rate: Decimal
    source: str
    effective_at: datetime


class Conversion(BaseModel):
    """An indicative equivalent — never a price the lister set."""

    amount: Decimal
    currency: str
    converted: Decimal | None
    to: str
    indicative: bool = True
    rate: RateOut | None
    note: str


def latest_rate(db: Session, base: str, quote: str, at: datetime | None = None) -> RateOut | None:
    """Most recent rate for the pair (direct, or the inverse of the reverse pair)."""
    at = at or datetime.now(UTC)

    def fetch(b: str, q: str) -> ExchangeRate | None:
        return db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.base == b, ExchangeRate.quote == q, ExchangeRate.effective_at <= at)
            .order_by(ExchangeRate.effective_at.desc(), ExchangeRate.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    direct, reverse = fetch(base, quote), fetch(quote, base)
    candidates: list[RateOut] = []
    if direct:
        candidates.append(RateOut.model_validate(direct))
    if reverse:
        candidates.append(
            RateOut(
                base=base,
                quote=quote,
                rate=(Decimal(1) / reverse.rate).quantize(Decimal("0.000001")),
                source=reverse.source,
                effective_at=reverse.effective_at,
            )
        )
    return max(candidates, key=lambda r: r.effective_at) if candidates else None


def convert(db: Session, amount: Decimal, from_: str, to: str) -> Conversion:
    if from_ == to:
        return Conversion(
            amount=amount, currency=from_, converted=amount, to=to, rate=None, note="same currency"
        )
    rate = latest_rate(db, from_, to)
    if rate is None:
        return Conversion(
            amount=amount,
            currency=from_,
            converted=None,
            to=to,
            rate=None,
            note="No exchange rate is configured; no conversion shown.",
        )
    places = Decimal("1") if to == "IQD" else Decimal("0.01")
    return Conversion(
        amount=amount,
        currency=from_,
        converted=(amount * rate.rate).quantize(places, rounding=ROUND_HALF_UP),
        to=to,
        rate=rate,
        note=f"Indicative only, at the {rate.source} rate of {rate.effective_at.date()}.",
    )


router = APIRouter(tags=["money"])


@router.get("/exchange-rates/latest", response_model=RateOut | None)
def get_latest(
    base: Currency = "USD", quote: Currency = "IQD", db: Session = Depends(get_db)
) -> RateOut | None:
    if base == quote:
        raise AppError("base and quote must differ", code="VALIDATION_ERROR", status_code=422)
    return latest_rate(db, base, quote)


@router.get("/exchange-rates/convert", response_model=Conversion)
def get_conversion(
    amount: Decimal = Query(ge=0, le=Decimal("1e15")),
    from_: Currency = Query(alias="from"),
    to: Currency = Query(),
    db: Session = Depends(get_db),
) -> Conversion:
    return convert(db, amount, from_, to)


@router.post("/admin/exchange-rates", response_model=RateOut, status_code=status.HTTP_201_CREATED)
def add_rate(
    body: RateIn,
    principal: Principal = Depends(require_permission(Permission.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
) -> RateOut:
    if body.base == body.quote:
        raise AppError("base and quote must differ", code="VALIDATION_ERROR", status_code=422)
    row = ExchangeRate(
        base=body.base,
        quote=body.quote,
        rate=body.rate,
        source=body.source.strip(),
        effective_at=body.effective_at or datetime.now(UTC),
        created_by_id=principal.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        "exchange_rate.added",
        actor_id=principal.id,
        resource_type="exchange_rate",
        resource_id=row.id,
        data={"pair": f"{row.base}/{row.quote}", "rate": str(row.rate), "source": row.source},
    )
    db.commit()
    return RateOut.model_validate(row)
