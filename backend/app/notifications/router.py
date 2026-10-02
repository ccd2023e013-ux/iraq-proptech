"""/api/v1 notifications, preferences, push subscriptions, webhooks admin, jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal, get_principal, require_permission
from app.core.errors import AppError, NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.notifications import service, webhooks
from app.notifications.models import (
    Category,
    JobRun,
    Notification,
    NotificationDelivery,
    PushSubscription,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.rbac.catalog import Permission

router = APIRouter(tags=["notifications"])


# --- in-app notifications


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    category: str
    title_ar: str
    title_en: str
    body_ar: str | None
    body_en: str | None
    link: str | None
    read_at: datetime | None
    created_at: datetime


@router.get("/me/notifications", response_model=Page[NotificationOut])
def my_notifications(
    unread_only: bool = False,
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Page[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == principal.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Notification.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars()
    return Page(
        items=[NotificationOut.model_validate(n) for n in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/me/notifications/unread-count")
def unread_count(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> dict[str, int]:
    count = db.execute(
        select(func.count()).where(
            Notification.user_id == principal.id, Notification.read_at.is_(None)
        )
    ).scalar_one()
    return {"unread": int(count)}


@router.post("/me/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    notification_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != principal.id:
        raise NotFoundError("Notification not found", code="NOTIFICATION_NOT_FOUND")
    notification.read_at = notification.read_at or datetime.now(UTC)
    db.commit()


@router.post("/me/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == principal.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()


# --- preferences


class PreferencesIO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False
    categories: dict[str, bool] = Field(default_factory=dict)

    @field_validator("categories")
    @classmethod
    def _known(cls, value: dict[str, bool]) -> dict[str, bool]:
        known = {c.value for c in Category}
        unknown = set(value) - known
        if unknown:
            raise ValueError(f"unknown categories: {sorted(unknown)}")
        return value


@router.get("/me/notification-preferences", response_model=PreferencesIO)
def get_preferences(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> PreferencesIO:
    pref = service.preferences(db, principal.id)
    db.commit()
    return PreferencesIO(
        email_enabled=pref.email_enabled,
        sms_enabled=pref.sms_enabled,
        push_enabled=pref.push_enabled,
        categories=pref.categories,
    )


@router.put("/me/notification-preferences", response_model=PreferencesIO)
def put_preferences(
    body: PreferencesIO,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> PreferencesIO:
    if body.sms_enabled and not principal.user.phone:
        raise AppError("Add a phone number first", code="PHONE_REQUIRED", status_code=422)
    pref = service.preferences(db, principal.id)
    pref.email_enabled = body.email_enabled
    pref.sms_enabled = body.sms_enabled
    pref.push_enabled = body.push_enabled
    pref.categories = dict(body.categories)
    db.commit()
    return body


# --- push subscriptions (Web Push architecture)


class PushIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=10, max_length=500, pattern=r"^https://")
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


@router.post("/me/push-subscriptions", status_code=status.HTTP_201_CREATED)
def add_push(
    body: PushIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> dict[str, str]:
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    ).scalar_one_or_none()
    if existing is None:
        existing = PushSubscription(user_id=principal.id, **body.model_dump())
        db.add(existing)
    else:
        existing.user_id = principal.id  # the device now belongs to this account
        existing.p256dh, existing.auth = body.p256dh, body.auth
    db.commit()
    return {"id": str(existing.id)}


@router.delete("/me/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def remove_push(
    endpoint: str = Query(max_length=500),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    sub = db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint, PushSubscription.user_id == principal.id
        )
    ).scalar_one_or_none()
    if sub is not None:
        db.delete(sub)
        db.commit()


# --- webhooks (admin)

_automation = require_permission(Permission.AUTOMATION_MANAGE)


def validate_events(value: list[str]) -> list[str]:
    allowed = set(webhooks.WEBHOOK_EVENTS) | {"*"}
    bad = [e for e in value if e not in allowed]
    if bad:
        raise ValueError(f"unknown events: {bad}")
    if not value:
        raise ValueError("choose at least one event")
    return sorted(set(value))


class WebhookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    url: str = Field(min_length=10, max_length=500)
    events: list[str] = Field(min_length=1, max_length=len(webhooks.WEBHOOK_EVENTS) + 1)

    @field_validator("events")
    @classmethod
    def _events(cls, value: list[str]) -> list[str]:
        return validate_events(value)


class WebhookPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("events")
    @classmethod
    def _events(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else validate_events(value)


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    events: list[str]
    is_active: bool
    consecutive_failures: int
    last_status: int | None
    last_delivery_at: datetime | None
    created_at: datetime


class WebhookCreated(WebhookOut):
    secret: str = Field(description="Shown once. Store it to verify signatures.")


def _check(url: str) -> None:
    try:
        webhooks.check_url(url)
    except webhooks.UnsafeURLError as exc:
        raise AppError(str(exc), code="UNSAFE_URL", status_code=422) from exc


@router.get("/admin/webhooks/events")
def webhook_events(_: Principal = Depends(_automation)) -> list[str]:
    return webhooks.WEBHOOK_EVENTS


@router.get("/admin/webhooks", response_model=list[WebhookOut])
def list_webhooks(
    _: Principal = Depends(_automation), db: Session = Depends(get_db)
) -> list[WebhookOut]:
    rows = db.execute(select(WebhookEndpoint).order_by(WebhookEndpoint.created_at)).scalars()
    return [WebhookOut.model_validate(w) for w in rows]


@router.post("/admin/webhooks", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
def create_webhook(
    body: WebhookIn, principal: Principal = Depends(_automation), db: Session = Depends(get_db)
) -> WebhookCreated:
    _check(body.url)
    endpoint = WebhookEndpoint(
        name=body.name.strip(),
        url=body.url,
        secret=service.new_webhook_secret(),
        events=body.events,
        is_active=True,
        created_by_id=principal.id,
        consecutive_failures=0,
    )
    db.add(endpoint)
    db.flush()
    audit.record(
        db,
        "webhook.created",
        actor_id=principal.id,
        resource_type="webhook",
        resource_id=endpoint.id,
        data={"events": ",".join(body.events)},
    )
    db.commit()
    db.refresh(endpoint)
    return WebhookCreated(
        **WebhookOut.model_validate(endpoint).model_dump(), secret=endpoint.secret
    )


def _get_webhook(db: Session, webhook_id: uuid.UUID) -> WebhookEndpoint:
    endpoint = db.get(WebhookEndpoint, webhook_id)
    if endpoint is None:
        raise NotFoundError("Webhook not found", code="WEBHOOK_NOT_FOUND")
    return endpoint


@router.patch("/admin/webhooks/{webhook_id}", response_model=WebhookOut)
def patch_webhook(
    webhook_id: uuid.UUID,
    body: WebhookPatch,
    principal: Principal = Depends(_automation),
    db: Session = Depends(get_db),
) -> WebhookOut:
    endpoint = _get_webhook(db, webhook_id)
    if body.name is not None:
        endpoint.name = body.name.strip()
    if body.events is not None:
        endpoint.events = body.events
    if body.is_active is not None:
        endpoint.is_active = body.is_active
        if body.is_active:
            endpoint.consecutive_failures = 0
    audit.record(
        db,
        "webhook.updated",
        actor_id=principal.id,
        resource_type="webhook",
        resource_id=endpoint.id,
    )
    db.commit()
    db.refresh(endpoint)
    return WebhookOut.model_validate(endpoint)


@router.delete("/admin/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: uuid.UUID,
    principal: Principal = Depends(_automation),
    db: Session = Depends(get_db),
) -> None:
    endpoint = _get_webhook(db, webhook_id)
    db.delete(endpoint)
    audit.record(
        db,
        "webhook.deleted",
        actor_id=principal.id,
        resource_type="webhook",
        resource_id=webhook_id,
    )
    db.commit()


@router.post("/admin/webhooks/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
def test_webhook(
    webhook_id: uuid.UUID,
    principal: Principal = Depends(_automation),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    endpoint = _get_webhook(db, webhook_id)
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event="webhook.test",
        payload={"event": "webhook.test", "occurred_at": datetime.now(UTC).isoformat(), "data": {}},
        status="PENDING",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(delivery)
    db.info["notifications_pending"] = True
    db.commit()
    return {"delivery_id": str(delivery.id)}


class WebhookDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event: str
    status: str
    attempts: int
    response_status: int | None
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None


@router.get("/admin/webhooks/{webhook_id}/deliveries", response_model=list[WebhookDeliveryOut])
def webhook_deliveries(
    webhook_id: uuid.UUID, _: Principal = Depends(_automation), db: Session = Depends(get_db)
) -> list[WebhookDeliveryOut]:
    _get_webhook(db, webhook_id)
    rows = db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(100)
    ).scalars()
    return [WebhookDeliveryOut.model_validate(r) for r in rows]


# --- operations


@router.get("/admin/jobs")
def admin_jobs(
    _: Principal = Depends(_automation), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = db.execute(select(JobRun).order_by(JobRun.started_at.desc()).limit(100)).scalars()
    return [
        {
            "id": str(j.id),
            "name": j.name,
            "status": j.status,
            "detail": j.detail,
            "error": j.error,
            "started_at": j.started_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        }
        for j in rows
    ]


@router.get("/admin/notifications/deliveries")
def admin_deliveries(
    delivery_status: str | None = Query(default=None, alias="status", max_length=8),
    _: Principal = Depends(_automation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    counts: dict[str, int] = {
        str(k): int(v)
        for k, v in db.execute(
            select(NotificationDelivery.status, func.count()).group_by(NotificationDelivery.status)
        ).all()
    }
    stmt = select(NotificationDelivery).order_by(NotificationDelivery.created_at.desc()).limit(50)
    if delivery_status:
        stmt = stmt.where(NotificationDelivery.status == delivery_status)
    recent = [
        {
            "id": str(d.id),
            "channel": d.channel,
            "status": d.status,
            "attempts": d.attempts,
            "provider": d.provider,
            "last_error": d.last_error,
            "created_at": d.created_at.isoformat(),
        }
        for d in db.execute(stmt).scalars()
    ]
    return {"counts": counts, "recent": recent}
