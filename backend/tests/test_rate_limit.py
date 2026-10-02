"""Rate limiting on sensitive endpoints (enabled explicitly for this module)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

pytestmark = pytest.mark.db


@pytest.fixture
def rate_limits_on() -> Iterator[None]:
    settings = get_settings()
    previous = settings.rate_limit_enabled
    settings.rate_limit_enabled = True
    yield
    settings.rate_limit_enabled = previous


def test_login_is_rate_limited_per_account(api: TestClient, rate_limits_on: None) -> None:
    email = f"target-{uuid.uuid4().hex[:8]}@example.com"
    statuses = [
        api.post(
            "/api/v1/auth/login", json={"email": email, "password": "Wrong-pass-123"}
        ).status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_forgot_password_is_rate_limited_per_account(api: TestClient, rate_limits_on: None) -> None:
    email = f"target-{uuid.uuid4().hex[:8]}@example.com"
    statuses = [
        api.post("/api/v1/auth/password/forgot", json={"email": email}).status_code
        for _ in range(4)
    ]
    assert statuses == [202, 202, 202, 429]
    body = api.post("/api/v1/auth/password/forgot", json={"email": email}).json()
    assert body["error"]["code"] == "RATE_LIMITED"
