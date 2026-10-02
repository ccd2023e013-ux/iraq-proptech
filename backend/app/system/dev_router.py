"""Development-only endpoints. Never mounted when APP_ENV=production."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.notifications.email import MockEmailProvider, get_email_provider

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
