"""Billing workflows: checkout, idempotent fulfilment, refunds, credits, expiry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import events
from app.audit import service as audit
from app.auth.deps import Principal
from app.billing.models import (
    Payment,
    PaymentStatus,
    Plan,
    PlanKind,
    Promotion,
    Subscription,
    SubscriptionStatus,
)
from app.billing.providers import get_provider
from app.core.errors import AppError, ConflictError, NotFoundError
from app.policies import can_manage_property
from app.properties.enums import PropertyStatus
from app.properties.models import Property

# One plan credit features one listing for this many days.
CREDIT_FEATURE_DAYS = 7


def _now() -> datetime:
    return datetime.now(UTC)


def active_subscription(db: Session, user_id: uuid.UUID) -> Subscription | None:
    return db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id, Subscription.status == SubscriptionStatus.ACTIVE
        )
    ).scalar_one_or_none()


def _promotable(db: Session, principal: Principal, property_id: uuid.UUID) -> Property:
    prop = db.get(Property, property_id)
    if (
        prop is None
        or prop.deleted_at is not None
        or not can_manage_property(
            db,
            principal,
            lister_id=prop.lister_id,
            agency_id=prop.agency_id,
            agent_id=prop.agent_id,
        )
    ):
        raise NotFoundError("Property not found")
    if prop.status != PropertyStatus.APPROVED:
        raise AppError("Only published listings can be promoted", code="NOT_PUBLISHED")
    return prop


def checkout(
    db: Session, principal: Principal, plan_code: str, property_id: uuid.UUID | None
) -> tuple[Payment, str]:
    provider = get_provider()
    plan = db.execute(
        select(Plan).where(Plan.code == plan_code, Plan.is_active.is_(True))
    ).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan not found")
    if plan.kind == PlanKind.PROMOTION:
        if property_id is None:
            raise AppError("Choose the listing to promote", code="PROPERTY_REQUIRED")
        _promotable(db, principal, property_id)
    else:
        property_id = None
        if active_subscription(db, principal.id) is not None:
            raise ConflictError(
                "You already have an active subscription", code="ALREADY_SUBSCRIBED"
            )
    payment = Payment(
        user_id=principal.id,
        plan_id=plan.id,
        property_id=property_id,
        amount=plan.price_amount,
        currency=plan.currency,
        provider=provider.name,
        status=PaymentStatus.PENDING,
        is_demo=provider.is_demo,
    )
    db.add(payment)
    db.flush()
    session = provider.create_checkout(str(payment.id), str(plan.price_amount), plan.currency)
    payment.provider_ref = session.provider_ref
    audit.record(
        db,
        "billing.checkout",
        actor_id=principal.id,
        resource_type="payment",
        resource_id=payment.id,
        data={"plan": plan.code, "demo": provider.is_demo},
    )
    db.commit()
    return payment, session.redirect_url


def complete(
    db: Session, payment_id: uuid.UUID, *, succeeded: bool, reason: str | None = None
) -> Payment:
    """Apply a provider outcome exactly once (row lock; repeated callbacks are no-ops)."""
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.status != PaymentStatus.PENDING:
        return payment
    now = _now()
    if not succeeded:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = (reason or "declined")[:200]
        db.commit()
        return payment
    plan = db.get(Plan, payment.plan_id)
    assert plan is not None  # noqa: S101 - FK
    payment.status = PaymentStatus.SUCCEEDED
    payment.paid_at = now
    if plan.kind == PlanKind.SUBSCRIPTION:
        if active_subscription(db, payment.user_id) is not None:
            # Paid twice for a subscription: keep the money traceable, flag for refund.
            payment.failure_reason = "duplicate subscription payment — refund required"
        else:
            db.add(
                Subscription(
                    user_id=payment.user_id,
                    plan_id=plan.id,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=plan.duration_days),
                    credits_remaining=plan.featured_credits,
                    last_payment_id=payment.id,
                    is_demo=payment.is_demo,
                )
            )
    elif payment.property_id is not None:
        _feature(
            db,
            payment.property_id,
            days=plan.duration_days,
            payment_id=payment.id,
            subscription_id=None,
            actor_id=payment.user_id,
            is_demo=payment.is_demo,
        )
    audit.record(
        db,
        "billing.payment_succeeded",
        actor_id=payment.user_id,
        resource_type="payment",
        resource_id=payment.id,
        data={"plan": plan.code, "amount": str(payment.amount), "currency": payment.currency},
    )
    events.emit(
        db,
        "payment.succeeded",
        {
            "payment_id": str(payment.id),
            "user_id": str(payment.user_id),
            "plan": plan.code,
            "demo": payment.is_demo,
        },
    )
    db.commit()
    return payment


def _feature(
    db: Session,
    property_id: uuid.UUID,
    *,
    days: int,
    payment_id: uuid.UUID | None,
    subscription_id: uuid.UUID | None,
    actor_id: uuid.UUID,
    is_demo: bool,
) -> Promotion:
    prop = db.execute(
        select(Property).where(Property.id == property_id).with_for_update()
    ).scalar_one()
    now = _now()
    start = max(now, prop.featured_until) if prop.featured_until else now
    promo = Promotion(
        property_id=prop.id,
        starts_at=start,
        ends_at=start + timedelta(days=days),
        payment_id=payment_id,
        subscription_id=subscription_id,
        created_by_id=actor_id,
        is_demo=is_demo,
    )
    db.add(promo)
    prop.featured_until = promo.ends_at
    return promo


def redeem_credit(db: Session, principal: Principal, property_id: uuid.UUID) -> Promotion:
    _promotable(db, principal, property_id)
    sub = db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == principal.id, Subscription.status == SubscriptionStatus.ACTIVE
        )
        .with_for_update()
    ).scalar_one_or_none()
    if sub is None or sub.credits_remaining <= 0:
        raise AppError("No featured credits left", code="NO_CREDITS", status_code=402)
    sub.credits_remaining -= 1
    promo = _feature(
        db,
        property_id,
        days=CREDIT_FEATURE_DAYS,
        payment_id=None,
        subscription_id=sub.id,
        actor_id=principal.id,
        is_demo=sub.is_demo,
    )
    audit.record(
        db,
        "billing.credit_redeemed",
        actor_id=principal.id,
        resource_type="property",
        resource_id=property_id,
        data={"subscription_id": str(sub.id)},
    )
    db.commit()
    return promo


def refund(db: Session, actor: Principal, payment_id: uuid.UUID, reason: str) -> Payment:
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise ConflictError("Only successful payments can be refunded", code="NOT_REFUNDABLE")
    get_provider().refund(payment.provider_ref)
    now = _now()
    payment.status = PaymentStatus.REFUNDED
    payment.refunded_at = now
    # Withdraw what the payment bought.
    for promo in db.execute(
        select(Promotion).where(Promotion.payment_id == payment.id, Promotion.canceled_at.is_(None))
    ).scalars():
        promo.canceled_at = now
        _recompute_featured(db, promo.property_id, now)
    db.execute(
        update(Subscription)
        .where(
            Subscription.last_payment_id == payment.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .values(status=SubscriptionStatus.CANCELED, current_period_end=now)
    )
    audit.record(
        db,
        "billing.payment_refunded",
        actor_id=actor.id,
        resource_type="payment",
        resource_id=payment.id,
        data={"reason": reason[:300]},
    )
    db.commit()
    return payment


def _recompute_featured(db: Session, property_id: uuid.UUID, now: datetime) -> None:
    db.flush()
    latest = db.execute(
        select(Promotion.ends_at)
        .where(
            Promotion.property_id == property_id,
            Promotion.canceled_at.is_(None),
            Promotion.ends_at > now,
        )
        .order_by(Promotion.ends_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    prop = db.get(Property, property_id)
    if prop is not None:
        prop.featured_until = latest


def cancel_subscription(db: Session, principal: Principal) -> Subscription:
    sub = active_subscription(db, principal.id)
    if sub is None:
        raise NotFoundError("No active subscription")
    sub.cancel_at_period_end = True
    audit.record(
        db,
        "billing.subscription_cancel_requested",
        actor_id=principal.id,
        resource_type="subscription",
        resource_id=sub.id,
    )
    db.commit()
    return sub


def expire_subscriptions(db: Session) -> dict[str, Any]:
    """Period ended → EXPIRED (or CANCELED if cancellation was requested). No auto-renewal
    in DEMO mode; real providers would renew via their recurring-billing callbacks."""
    now = _now()
    subs = list(
        db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.current_period_end <= now,
            )
        ).scalars()
    )
    for sub in subs:
        sub.status = (
            SubscriptionStatus.CANCELED if sub.cancel_at_period_end else SubscriptionStatus.EXPIRED
        )
    db.commit()
    return {"expired": len(subs)}
