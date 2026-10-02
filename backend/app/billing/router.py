"""Billing API: plans, checkout, demo payment simulation, my billing, admin."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal, get_principal, require_permission
from app.billing import service
from app.billing.models import Payment, PaymentStatus, Plan, PlanKind, Promotion, Subscription
from app.billing.providers import BillingDisabledError, billing_enabled, get_provider
from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.properties.models import Property
from app.properties.presenter import to_cards
from app.properties.schemas import PropertyCard
from app.rbac.catalog import Permission

router = APIRouter(tags=["billing"])
_manage = require_permission(Permission.BILLING_MANAGE)


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    kind: str
    name_ar: str
    name_en: str
    description_ar: str | None
    description_en: str | None
    price_amount: Decimal
    currency: str
    duration_days: int
    featured_credits: int
    is_active: bool
    is_demo: bool
    sort_order: int


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    property_id: uuid.UUID | None
    amount: Decimal
    currency: str
    provider: str
    status: str
    is_demo: bool
    failure_reason: str | None
    created_at: datetime
    paid_at: datetime | None
    refunded_at: datetime | None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    credits_remaining: int
    is_demo: bool


class PromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    canceled_at: datetime | None
    is_demo: bool


def _provider_guard() -> None:
    try:
        get_provider()
    except BillingDisabledError as exc:
        raise AppError(str(exc), code="BILLING_DISABLED", status_code=503) from exc


# --- public ---------------------------------------------------------------------


@router.get("/billing/config")
def billing_config() -> dict[str, Any]:
    enabled = billing_enabled()
    provider = get_settings().effective_payment_provider
    return {"enabled": enabled, "provider": provider, "demo": enabled and provider == "demo"}


@router.get("/billing/plans", response_model=list[PlanOut])
def public_plans(db: Session = Depends(get_db)) -> list[PlanOut]:
    rows = db.execute(
        select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order, Plan.price_amount)
    ).scalars()
    return [PlanOut.model_validate(p) for p in rows]


@router.get("/properties/featured", response_model=list[PropertyCard])
def featured_properties(limit: int = 8, db: Session = Depends(get_db)) -> list[PropertyCard]:
    """Currently promoted listings (labelled as promoted wherever shown)."""
    rows = list(
        db.execute(
            select(Property)
            .where(
                Property.status == "APPROVED",
                Property.deleted_at.is_(None),
                Property.featured_until > datetime.now(UTC),
            )
            .order_by(func.random())
            .limit(max(1, min(limit, 24)))
        ).scalars()
    )
    return to_cards(db, rows)


# --- customer --------------------------------------------------------------------


class CheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=1, max_length=40)
    property_id: uuid.UUID | None = None


@router.post(
    "/billing/checkout",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("billing-checkout", limit=30, window=3600))],
)
def create_checkout(
    body: CheckoutIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> dict[str, Any]:
    _provider_guard()
    payment, redirect_url = service.checkout(db, principal, body.plan_code, body.property_id)
    return {"payment": PaymentOut.model_validate(payment), "redirect_url": redirect_url}


def _my_payment(db: Session, principal: Principal, payment_id: uuid.UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None or payment.user_id != principal.id:
        raise NotFoundError("Payment not found")
    return payment


@router.get("/billing/payments/{payment_id}")
def get_payment(
    payment_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payment = _my_payment(db, principal, payment_id)
    plan = db.get(Plan, payment.plan_id)
    return {
        "payment": PaymentOut.model_validate(payment),
        "plan": PlanOut.model_validate(plan) if plan else None,
    }


class DemoOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["SUCCEEDED", "FAILED"]


@router.post("/billing/payments/{payment_id}/demo-complete", response_model=PaymentOut)
def demo_complete(
    payment_id: uuid.UUID,
    body: DemoOutcome,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> PaymentOut:
    """Simulate the provider's answer. Only for DEMO payments, only by the payer."""
    payment = _my_payment(db, principal, payment_id)
    if payment.provider != "demo" or not payment.is_demo:
        raise NotFoundError("Payment not found")
    _provider_guard()
    done = service.complete(
        db, payment.id, succeeded=body.outcome == "SUCCEEDED", reason="demo: simulated decline"
    )
    return PaymentOut.model_validate(done)


@router.get("/me/billing")
def my_billing(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sub = service.active_subscription(db, principal.id)
    payments = db.execute(
        select(Payment)
        .where(Payment.user_id == principal.id)
        .order_by(Payment.created_at.desc())
        .limit(50)
    ).scalars()
    promos = db.execute(
        select(Promotion)
        .where(Promotion.created_by_id == principal.id)
        .order_by(Promotion.created_at.desc())
        .limit(50)
    ).scalars()
    plan_ids = {sub.plan_id} if sub else set()
    plans = {p.id: p for p in db.execute(select(Plan).where(Plan.id.in_(plan_ids))).scalars()}
    return {
        "subscription": SubscriptionOut.model_validate(sub) if sub else None,
        "subscription_plan": PlanOut.model_validate(plans[sub.plan_id]) if sub else None,
        "payments": [PaymentOut.model_validate(p) for p in payments],
        "promotions": [PromotionOut.model_validate(p) for p in promos],
    }


@router.post("/me/subscription/cancel", response_model=SubscriptionOut)
def cancel_subscription(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> SubscriptionOut:
    return SubscriptionOut.model_validate(service.cancel_subscription(db, principal))


class RedeemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: uuid.UUID


@router.post(
    "/billing/promotions/redeem", response_model=PromotionOut, status_code=status.HTTP_201_CREATED
)
def redeem(
    body: RedeemIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> PromotionOut:
    return PromotionOut.model_validate(service.redeem_credit(db, principal, body.property_id))


# --- admin ----------------------------------------------------------------------


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_\-]+$")
    kind: PlanKind
    name_ar: str = Field(min_length=1, max_length=120)
    name_en: str = Field(min_length=1, max_length=120)
    description_ar: str | None = Field(default=None, max_length=2000)
    description_en: str | None = Field(default=None, max_length=2000)
    price_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    currency: Literal["IQD", "USD"]
    duration_days: int = Field(ge=1, le=366)
    featured_credits: int = Field(default=0, ge=0, le=1000)
    is_active: bool = True
    is_demo: bool = False
    sort_order: int = Field(default=0, ge=0, le=1000)


class PlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_ar: str | None = Field(default=None, min_length=1, max_length=120)
    name_en: str | None = Field(default=None, min_length=1, max_length=120)
    description_ar: str | None = Field(default=None, max_length=2000)
    description_en: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)


@router.get("/admin/billing/plans", response_model=list[PlanOut])
def admin_plans(_: Principal = Depends(_manage), db: Session = Depends(get_db)) -> list[PlanOut]:
    rows = db.execute(select(Plan).order_by(Plan.sort_order, Plan.code)).scalars()
    return [PlanOut.model_validate(p) for p in rows]


@router.post("/admin/billing/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def admin_create_plan(
    body: PlanIn, principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> PlanOut:
    plan = Plan(**body.model_dump())
    db.add(plan)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A plan with this code exists", code="PLAN_EXISTS") from exc
    audit.record(
        db,
        "billing.plan_created",
        actor_id=principal.id,
        resource_type="plan",
        resource_id=plan.id,
        data={"code": plan.code, "price": str(plan.price_amount), "currency": plan.currency},
    )
    db.commit()
    return PlanOut.model_validate(plan)


@router.patch("/admin/billing/plans/{plan_id}", response_model=PlanOut)
def admin_update_plan(
    plan_id: uuid.UUID,
    body: PlanPatch,
    principal: Principal = Depends(_manage),
    db: Session = Depends(get_db),
) -> PlanOut:
    """Prices are immutable once created (payments reference them): create a new plan
    and deactivate the old one instead."""
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("Plan not found")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(plan, key, value)
    audit.record(
        db,
        "billing.plan_updated",
        actor_id=principal.id,
        resource_type="plan",
        resource_id=plan.id,
        data={k: str(v) for k, v in changes.items()},
    )
    db.commit()
    return PlanOut.model_validate(plan)


@router.get("/admin/billing/payments", response_model=Page[PaymentOut])
def admin_payments(
    payment_status: PaymentStatus | None = None,
    params: PageParams = Depends(page_params),
    _: Principal = Depends(_manage),
    db: Session = Depends(get_db),
) -> Page[PaymentOut]:
    stmt = select(Payment)
    if payment_status is not None:
        stmt = stmt.where(Payment.status == payment_status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Payment.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars()
    return Page[PaymentOut](
        items=[PaymentOut.model_validate(p) for p in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


class RefundIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=300)


@router.post("/admin/billing/payments/{payment_id}/refund", response_model=PaymentOut)
def admin_refund(
    payment_id: uuid.UUID,
    body: RefundIn,
    principal: Principal = Depends(_manage),
    db: Session = Depends(get_db),
) -> PaymentOut:
    return PaymentOut.model_validate(service.refund(db, principal, payment_id, body.reason))


@router.get("/admin/billing/summary")
def admin_summary(_: Principal = Depends(_manage), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Revenue by currency and DEMO flag — demo money is never added to real revenue."""
    rows = db.execute(
        select(Payment.currency, Payment.is_demo, func.count(), func.sum(Payment.amount))
        .where(Payment.status == PaymentStatus.SUCCEEDED)
        .group_by(Payment.currency, Payment.is_demo)
    ).all()
    active = db.execute(select(func.count()).where(Subscription.status == "ACTIVE")).scalar_one()
    return {
        "revenue": [
            {"currency": c, "is_demo": d, "payments": int(n), "amount": str(a or 0)}
            for c, d, n, a in rows
        ],
        "active_subscriptions": int(active),
    }
