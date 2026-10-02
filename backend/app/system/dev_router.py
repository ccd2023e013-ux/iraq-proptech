"""Development-only endpoints. Never mounted when APP_ENV=production."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.notifications.email import MockEmailProvider, get_email_provider
from app.notifications.models import NotificationDelivery
from app.users.models import User

router = APIRouter(prefix="/dev", tags=["development"])


class OutboxMessage(BaseModel):
    to: str
    subject: str
    text: str
    tags: list[str]
    created_at: datetime


@router.get("/outbox", response_model=list[OutboxMessage])
def mock_outbox() -> list[OutboxMessage]:
    """Emails captured by the MOCK email provider (newest first)."""
    provider = get_email_provider()
    if not isinstance(provider, MockEmailProvider):
        return []
    return [
        OutboxMessage(
            to=m.to, subject=m.subject, text=m.text, tags=list(m.tags), created_at=m.created_at
        )
        for m in reversed(provider.outbox())
    ]


class DeliveryOut(BaseModel):
    channel: str
    status: str
    subject: str | None
    body: str
    user_email: str
    created_at: datetime


@router.get("/deliveries", response_model=list[DeliveryOut])
def recent_deliveries(db: Session = Depends(get_db)) -> list[DeliveryOut]:
    """Notification deliveries (any channel, any provider), newest first — for MOCK mode."""
    rows = db.execute(
        select(NotificationDelivery, User.email)
        .join(User, User.id == NotificationDelivery.user_id)
        .order_by(NotificationDelivery.created_at.desc())
        .limit(100)
    ).all()
    return [
        DeliveryOut(
            channel=d.channel,
            status=d.status,
            subject=d.subject,
            body=d.body,
            user_email=email,
            created_at=d.created_at,
        )
        for d, email in rows
    ]
