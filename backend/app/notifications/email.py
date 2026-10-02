"""Email delivery behind a provider interface.

* ``MockEmailProvider`` (default, **MOCK**): logs the message and keeps it in an
  in-memory outbox so developers and tests can read it. Sends nothing.
* ``SMTPEmailProvider``: any SMTP server (a free mailbox, a self-hosted relay
  on the production PC, ...). No vendor SDK.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage as MimeMessage
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    tags: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EmailProvider(Protocol):
    name: str

    def send(self, message: EmailMessage) -> None: ...


class MockEmailProvider:
    """MOCK provider — nothing leaves the process."""

    name = "mock"

    def __init__(self, capacity: int = 200) -> None:
        self._outbox: deque[EmailMessage] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def send(self, message: EmailMessage) -> None:
        with self._lock:
            self._outbox.append(message)
        logger.info(
            "mock_email_sent",
            extra={"mock": True, "to_domain": message.to.split("@")[-1], "tags": message.tags},
        )
        if not get_settings().log_json:
            # Human-readable copy for local development consoles only.
            logger.info("[MOCK EMAIL] To: %s | %s\n%s", message.to, message.subject, message.text)

    def outbox(self) -> list[EmailMessage]:
        with self._lock:
            return list(self._outbox)

    def clear(self) -> None:
        with self._lock:
            self._outbox.clear()


class SMTPEmailProvider:
    name = "smtp"

    def send(self, message: EmailMessage) -> None:
        settings = get_settings()
        if not settings.smtp_host:
            raise RuntimeError("SMTP_HOST is not configured")
        mime = MimeMessage()
        mime["From"] = settings.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(mime)


@lru_cache
def get_email_provider() -> EmailProvider:
    if get_settings().email_provider == "smtp":
        return SMTPEmailProvider()
    return MockEmailProvider()
