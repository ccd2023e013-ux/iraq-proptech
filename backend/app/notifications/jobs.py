"""Scheduled jobs: saved-search alerts, follow-up and task reminders, listing expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import events
from app.crm.models import CrmTask, Lead
from app.notifications import service
from app.notifications.models import Category
from app.properties.models import Property
from app.search import service as search_service
from app.search.saved import AlertFrequency, SavedSearch
from app.search.schemas import SearchFilters

INTERVALS = {
    AlertFrequency.INSTANT: timedelta(minutes=0),
    AlertFrequency.DAILY: timedelta(days=1),
    AlertFrequency.WEEKLY: timedelta(days=7),
}


def _now() -> datetime:
    return datetime.now(UTC)


def saved_search_alerts(db: Session, frequency: AlertFrequency) -> dict[str, Any]:
    now = _now()
    due_before = now - INTERVALS[frequency]
    searches = list(
        db.execute(
            select(SavedSearch).where(
                SavedSearch.alert_frequency == frequency,
                (SavedSearch.last_alerted_at.is_(None))
                | (SavedSearch.last_alerted_at <= due_before),
            )
        ).scalars()
    )
    alerted = 0
    for saved in searches:
        since = saved.last_alerted_at or saved.created_at
        stmt, _ = search_service.build_query(SearchFilters.model_validate(saved.filters))
        count = db.execute(
            select(func.count()).select_from(
                stmt.order_by(None).where(Property.published_at > since).subquery()
            )
        ).scalar_one()
        if count:
            service.notify(
                db,
                saved.user_id,
                kind="saved_search.matches",
                category=Category.SAVED_SEARCHES,
                title=(
                    f"{count} عقار جديد يطابق «{saved.name}»",
                    f"{count} new listings match “{saved.name}”",
                ),
                link=f"/saved-searches?open={saved.id}",
                data={"saved_search_id": str(saved.id), "count": count},
                dedupe_key=f"saved:{saved.id}:{now:%Y%m%d%H%M}",
            )
            alerted += 1
        saved.last_alerted_at = now
    db.commit()
    return {"frequency": frequency.value, "checked": len(searches), "alerted": alerted}


def reminders(db: Session) -> dict[str, Any]:
    """Due follow-ups and tasks → one reminder each (deduplicated)."""
    now = _now()
    sent = 0
    leads = db.execute(
        select(Lead).where(
            Lead.closed_at.is_(None),
            Lead.next_follow_up_at.is_not(None),
            Lead.next_follow_up_at <= now,
            Lead.next_follow_up_at > now - timedelta(days=3),
        )
    ).scalars()
    for lead in leads:
        target = lead.assigned_to_id or lead.owner_user_id
        assert lead.next_follow_up_at is not None  # noqa: S101
        if service.notify(
            db,
            target,
            kind="reminder.follow_up",
            category=Category.REMINDERS,
            title=("موعد متابعة عميل", "Follow-up due"),
            link=f"/dashboard/crm/leads/{lead.id}",
            data={"lead_id": str(lead.id)},
            dedupe_key=f"followup:{lead.id}:{lead.next_follow_up_at.isoformat()}",
        ):
            sent += 1
    tasks = db.execute(
        select(CrmTask).where(
            CrmTask.completed_at.is_(None),
            CrmTask.due_at.is_not(None),
            CrmTask.due_at <= now + timedelta(minutes=15),
            CrmTask.due_at > now - timedelta(days=3),
            CrmTask.assigned_to_id.is_not(None),
        )
    ).scalars()
    for task in tasks:
        assert task.assigned_to_id is not None and task.due_at is not None  # noqa: S101
        if service.notify(
            db,
            task.assigned_to_id,
            kind="reminder.task",
            category=Category.REMINDERS,
            title=(f"مهمة مستحقة: {task.title}", f"Task due: {task.title}"),
            link="/dashboard/crm/tasks",
            data={"task_id": str(task.id)},
            dedupe_key=f"task:{task.id}:{task.due_at.isoformat()}",
        ):
            sent += 1
    db.commit()
    return {"reminders": sent}


def expire_listings(db: Session) -> dict[str, Any]:
    from app.properties.enums import PropertyStatus
    from app.properties.service import _record_status

    expired = list(
        db.execute(
            select(Property).where(
                Property.status == PropertyStatus.APPROVED,
                Property.deleted_at.is_(None),
                Property.expires_at.is_not(None),
                Property.expires_at < _now(),
            )
        ).scalars()
    )
    for prop in expired:
        _record_status(db, prop, PropertyStatus.EXPIRED, None, "expired")
        events.emit(
            db,
            "property.expired",
            {
                "property_id": str(prop.id),
                "lister_id": str(prop.lister_id),
                "agent_id": str(prop.agent_id) if prop.agent_id else None,
            },
        )
    db.commit()
    return {"expired": len(expired)}
