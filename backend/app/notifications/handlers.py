"""Domain events → in-app notifications (+ email/SMS/push per preferences) and webhooks.

Registered once at startup (API and worker). Handlers run inside the
transaction that produced the event, so a notification exists if and only if
the change it describes was committed.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app import events
from app.notifications import service
from app.notifications.models import Category

_installed = False


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def on_inquiry(db: Session, name: str, p: dict[str, Any]) -> None:
    if (assignee := _uuid(p.get("assigned_to_id"))) is not None:
        service.notify(
            db,
            assignee,
            kind="inquiry.received",
            category=Category.LEADS,
            title=("استفسار جديد عن إعلانك", "New inquiry about your listing"),
            body=("وصلك استفسار جديد. افتح العميل المحتمل للرد.", "Open the lead to reply."),
            link=f"/dashboard/crm/leads/{p['lead_id']}",
            data={"lead_id": p.get("lead_id"), "property_id": p.get("property_id")},
        )


def on_lead_assigned(db: Session, name: str, p: dict[str, Any]) -> None:
    if (assignee := _uuid(p.get("assigned_to_id"))) is not None:
        service.notify(
            db,
            assignee,
            kind="lead.assigned",
            category=Category.LEADS,
            title=("أُسند إليك عميل محتمل", "A lead was assigned to you"),
            link=f"/dashboard/crm/leads/{p['lead_id']}",
            data={"lead_id": p.get("lead_id")},
        )


def on_message(db: Session, name: str, p: dict[str, Any]) -> None:
    to_lister = p.get("recipient_side") == "lister"
    recipient = _uuid(p.get("lister_user_id") if to_lister else p.get("customer_user_id"))
    if recipient is None or str(recipient) == p.get("sender_id"):
        return
    service.notify(
        db,
        recipient,
        kind="message.received",
        category=Category.MESSAGES,
        title=("رسالة جديدة", "New message"),
        link=f"/messages/{p['conversation_id']}",
        data={"conversation_id": p.get("conversation_id")},
    )


_LISTING_TEXT = {
    "property.approved": (("تم نشر إعلانك", "Your listing is published"), None),
    "property.rejected": (
        ("تم رفض إعلانك", "Your listing was rejected"),
        ("راجع سبب الرفض وعدّل الإعلان ثم أعد إرساله.", "See the reason, edit and resubmit."),
    ),
    "property.suspended": (
        ("تم إيقاف إعلانك", "Your listing was suspended"),
        ("راجع سبب الإيقاف في لوحة التحكم.", "See the reason in your dashboard."),
    ),
    "property.expired": (
        ("انتهت مدة إعلانك", "Your listing has expired"),
        ("يمكنك تجديده من لوحة التحكم.", "You can renew it from your dashboard."),
    ),
}


def on_listing_status(db: Session, name: str, p: dict[str, Any]) -> None:
    title, body = _LISTING_TEXT[name]
    recipients = {_uuid(p.get("lister_id")), _uuid(p.get("agent_id"))} - {None}
    for user_id in recipients:
        assert user_id is not None  # noqa: S101
        service.notify(
            db,
            user_id,
            kind=name.replace("property.", "listing."),
            category=Category.LISTINGS,
            title=title,
            body=body or (None, None),
            link=f"/dashboard/properties/{p['property_id']}",
            data={"property_id": p.get("property_id"), "reason_code": p.get("reason_code")},
        )


def on_report_resolved(db: Session, name: str, p: dict[str, Any]) -> None:
    for reporter in {_uuid(r) for r in p.get("reporter_ids", [])} - {None}:
        assert reporter is not None  # noqa: S101
        service.notify(
            db,
            reporter,
            kind="report.closed",
            category=Category.REPORTS,
            title=("تمت مراجعة بلاغك", "Your report was reviewed"),
            body=(
                "شكراً لمساعدتك في إبقاء المنصة موثوقة.",
                "Thank you for helping keep listings trustworthy.",
            ),
            link="/notifications",
            data={"report_id": p.get("report_id"), "outcome": p.get("outcome")},
            channels=(),
        )


def on_any(db: Session, name: str, p: dict[str, Any]) -> None:
    service.fanout_webhooks(db, name, p)


def install() -> None:
    global _installed
    if _installed:
        return
    events.subscribe("inquiry.created", on_inquiry)
    events.subscribe("lead.assigned", on_lead_assigned)
    events.subscribe("message.created", on_message)
    for name in _LISTING_TEXT:
        events.subscribe(name, on_listing_status)
    events.subscribe("report.resolved", on_report_resolved)
    events.subscribe("*", on_any)
    service.install_after_commit_hook()
    _installed = True
