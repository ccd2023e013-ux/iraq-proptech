"""SMS and push providers (email lives in ``email.py``).

* SMS: ``mock`` (default, MOCK — nothing is sent; the delivery row is the
  record) or ``http`` — a generic JSON gateway adapter for any Iraqi or
  international SMS provider that accepts ``POST {to, text}`` with a bearer
  token (``SMS_GATEWAY_URL`` / ``SMS_GATEWAY_TOKEN``; REQUIRES CREDENTIALS).
* Push: ``mock`` only. Real Web Push needs VAPID keys and a Web Push library;
  subscriptions are already stored so an adapter can be added without schema
  changes.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ChannelError(Exception):
    pass


class SMSProvider(Protocol):
    name: str

    def send(self, to: str, text: str) -> None: ...


class MockSMSProvider:
    name = "mock"

    def send(self, to: str, text: str) -> None:
        logger.info("mock_sms_sent", extra={"mock": True, "to_suffix": to[-3:]})


class HttpSMSProvider:
    name = "http"

    def __init__(self, url: str, token: str, client: httpx.Client | None = None) -> None:
        self.url, self.token = url, token
        self.client = client or httpx.Client(timeout=15)

    def send(self, to: str, text: str) -> None:
        try:
            response = self.client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json={"to": to, "text": text},
            )
        except httpx.HTTPError as exc:
            raise ChannelError(f"sms gateway unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise ChannelError(f"sms gateway returned HTTP {response.status_code}")


class PushProvider(Protocol):
    name: str

    def send(self, endpoint: str, title: str, body: str) -> None: ...


class MockPushProvider:
    name = "mock"

    def send(self, endpoint: str, title: str, body: str) -> None:
        logger.info("mock_push_sent", extra={"mock": True})


def get_sms_provider() -> SMSProvider:
    settings = get_settings()
    if settings.sms_provider == "http" and settings.sms_gateway_url and settings.sms_gateway_token:
        return HttpSMSProvider(settings.sms_gateway_url, settings.sms_gateway_token)
    return MockSMSProvider()


def get_push_provider() -> PushProvider:
    return MockPushProvider()
