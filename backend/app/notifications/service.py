"""Notification and webhook services (outbox writers and delivery workers)."""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.notifications import webhooks
from app.notifications.channels import ChannelError, get_push_provider, get_sms_provider
from app.notifications.email import EmailMessage, get_email_provider
from app.notifications.models import (
    Category,
    Channel,
    DeliveryStatus,
    JobRun,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    PushSubscription,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.users.models import User

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BACKOFF_MINUTES = [1, 5, 15, 60, 240]
AUTO_DISABLE_AFTER = 20  # consecutive webhook failures


def _now() -> datetime:
    return datetime.now(UTC)


# --- preferences


def preferences(db: Session, user_id: uuid.UUID) -> NotificationPreference:
    pref = db.get(NotificationPreference, user_id)
    if pref is None:
        pref = NotificationPreference(
            user_id=user_id,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=False,
            categories={},
        )
        db.add(pref)
        db.flush()
    return pref


def _enabled(pref: NotificationPreference, category: str) -> bool:
    return bool(pref.categories.get(category, True))


# --- writing notifications (inside the caller's transaction)


def notify(
    db: Session,
    user_id: uuid.UUID,
    *,
    kind: str,
    category: Category,
    title: tuple[str, str],
    body: tuple[str | None, str | None] = (None, None),
    link: str | None = None,
    data: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    channels: tuple[Channel, ...] = (Channel.EMAIL,),
) -> Notification | None:
    """Create an in-app notification and queue external deliveries per preferences.

    Returns None when ``dedupe_key`` was already used for this user.
    """
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.status != "ACTIVE":
        return None
    values = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "kind": kind,
        "category": category.value,
        "title_ar": title[0][:200],
        "title_en": title[1][:200],
        "body_ar": body[0],
        "body_en": body[1],
        "link": link,
        "data": data,
        "dedupe_key": dedupe_key,
        "created_at": _now(),
    }
    stmt = insert(Notification).values(**values)
    if dedupe_key:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["user_id", "dedupe_key"],
            index_where=Notification.dedupe_key.is_not(None),
        )
    result = db.execute(stmt.returning(Notification.id))
    if result.scalar_one_or_none() is None:
        return None
    notification = db.get(Notification, values["id"])
    assert notification is not None  # noqa: S101
    pref = preferences(db, user_id)
    if not _enabled(pref, category.value):
        return notification
    arabic = user.preferred_locale != "en"
    subject = title[0] if arabic else title[1]
    text = (body[0] if arabic else body[1]) or ""
    if link:
        text = f"{text}\n\n{get_settings().frontend_url.rstrip('/')}{link}".strip()
    wanted = {
        Channel.EMAIL: pref.email_enabled and bool(user.email),
        Channel.SMS: pref.sms_enabled and bool(user.phone),
        Channel.PUSH: pref.push_enabled,
    }
    for channel in channels:
        if wanted.get(channel):
            db.add(
                NotificationDelivery(
                    notification_id=notification.id,
                    user_id=user_id,
                    channel=channel,
                    subject=subject,
                    body=text or subject,
                    status=DeliveryStatus.PENDING,
                    attempts=0,
                    next_attempt_at=_now(),
                )
            )
    db.info["notifications_pending"] = True
    return notification


def fanout_webhooks(db: Session, event: str, payload: dict[str, Any]) -> int:
    """Queue a delivery for every active endpoint subscribed to ``event``."""
    public_event = webhooks.EVENT_ALIASES.get(event, event)
    if public_event not in webhooks.WEBHOOK_EVENTS:
        return 0
    endpoints = db.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.is_active.is_(True))
    ).scalars()
    count = 0
    for endpoint in endpoints:
        if public_event in endpoint.events or "*" in endpoint.events:
            db.add(
                WebhookDelivery(
                    endpoint_id=endpoint.id,
                    event=public_event,
                    payload={
                        "event": public_event,
                        "occurred_at": _now().isoformat(),
                        "data": payload,
                    },
                    status=DeliveryStatus.PENDING,
                    attempts=0,
                    next_attempt_at=_now(),
                )
            )
            count += 1
    if count:
        db.info["notifications_pending"] = True
    return count


def new_webhook_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


# --- delivering (workers)


def _backoff(attempts: int) -> datetime:
    minutes = BACKOFF_MINUTES[min(attempts - 1, len(BACKOFF_MINUTES) - 1)]
    return _now() + timedelta(minutes=minutes)


def process_deliveries(db: Session, limit: int = 100) -> dict[str, int]:
    rows = list(
        db.execute(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.status == DeliveryStatus.PENDING,
                NotificationDelivery.next_attempt_at <= _now(),
            )
            .order_by(NotificationDelivery.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    stats = {"sent": 0, "failed": 0, "retry": 0, "skipped": 0}
    for delivery in rows:
        user = db.get(User, delivery.user_id)
        delivery.attempts += 1
        try:
            if user is None:
                raise ChannelError("user gone")
            if delivery.channel == Channel.EMAIL:
                provider = get_email_provider()
                provider.send(
                    EmailMessage(
                        to=user.email,
                        subject=delivery.subject or "",
                        text=delivery.body,
                        tags=("notification",),
                    )
                )
                delivery.provider = provider.name
            elif delivery.channel == Channel.SMS:
                if not user.phone:
                    delivery.status = DeliveryStatus.SKIPPED
                    stats["skipped"] += 1
                    continue
                sms = get_sms_provider()
                sms.send(user.phone, delivery.body[:600])
                delivery.provider = sms.name
            else:
                push = get_push_provider()
                subs = (
                    db.execute(select(PushSubscription).where(PushSubscription.user_id == user.id))
                    .scalars()
                    .all()
                )
                if not subs:
                    delivery.status = DeliveryStatus.SKIPPED
                    stats["skipped"] += 1
                    continue
                for sub in subs:
                    push.send(sub.endpoint, delivery.subject or "", delivery.body[:300])
                delivery.provider = push.name
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = _now()
            stats["sent"] += 1
        except Exception as exc:  # provider errors are recorded, never raised
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:300]
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.status = DeliveryStatus.FAILED
                stats["failed"] += 1
            else:
                delivery.next_attempt_at = _backoff(delivery.attempts)
                stats["retry"] += 1
    db.commit()
    return stats


def process_webhooks(
    db: Session, limit: int = 50, poster: Callable[..., int] = webhooks.post
) -> dict[str, int]:
    rows = list(
        db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == DeliveryStatus.PENDING,
                WebhookDelivery.next_attempt_at <= _now(),
            )
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    stats = {"sent": 0, "failed": 0, "retry": 0}
    for delivery in rows:
        endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
        if endpoint is None or not endpoint.is_active:
            delivery.status = DeliveryStatus.SKIPPED
            continue
        delivery.attempts += 1
        try:
            code = poster(
                endpoint.url, endpoint.secret, delivery.event, str(delivery.id), delivery.payload
            )
            delivery.response_status = code
            endpoint.last_status = code
            endpoint.last_delivery_at = _now()
            if 200 <= code < 300:
                delivery.status = DeliveryStatus.SENT
                delivery.sent_at = _now()
                endpoint.consecutive_failures = 0
                stats["sent"] += 1
                continue
            raise ChannelError(f"HTTP {code}")
        except Exception as exc:
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:300]
            endpoint.consecutive_failures += 1
            if endpoint.consecutive_failures >= AUTO_DISABLE_AFTER:
                endpoint.is_active = False  # stop hammering a dead endpoint
            if delivery.attempts >= MAX_ATTEMPTS or isinstance(exc, webhooks.UnsafeURLError):
                delivery.status = DeliveryStatus.FAILED
                stats["failed"] += 1
            else:
                delivery.next_attempt_at = _backoff(delivery.attempts)
                stats["retry"] += 1
    db.commit()
    return stats


# --- job runs


def run_job(db: Session, name: str, fn: Callable[[Session], dict[str, Any]]) -> JobRun:
    job = JobRun(name=name, status="RUNNING", started_at=_now())
    db.add(job)
    db.commit()
    try:
        detail = fn(db)
        job.status, job.detail = "SUCCEEDED", detail
    except Exception as exc:
        db.rollback()
        job = db.get(JobRun, job.id) or job
        job.status, job.error = "FAILED", f"{type(exc).__name__}: {exc}"[:300]
        logger.exception("job_failed", extra={"job": name})
    job.finished_at = _now()
    db.commit()
    return job


# --- after-commit kick: deliver promptly without waiting for the scheduler


def _kick(session: Session) -> None:
    if not session.info.pop("notifications_pending", False):
        return
    settings = get_settings()
    if settings.app_env == "test":
        return  # tests drive delivery explicitly
    if settings.notifications_inline:
        from app.db.session import get_sessionmaker

        try:
            with get_sessionmaker()() as db:
                process_deliveries(db)
                process_webhooks(db)
        except Exception:
            logger.exception("inline_delivery_failed")
        return
    try:
        from app.workers.celery_app import celery_app

        celery_app.send_task("notifications.deliver", retry=False)
    except Exception:
        logger.warning("delivery_kick_failed")  # the scheduler will pick it up


def install_after_commit_hook() -> None:
    if not sa_event.contains(Session, "after_commit", _kick):
        sa_event.listen(Session, "after_commit", _kick)
