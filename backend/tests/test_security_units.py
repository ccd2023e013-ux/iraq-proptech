"""Unit tests for security primitives (no database needed)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth.cookies import CSRF_COOKIE, CSRF_HEADER, enforce_csrf
from app.auth.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.core.errors import register_exception_handlers
from app.core.rate_limit import RateLimitedError, RateLimiter
from app.users.validation import normalize_iraqi_phone, password_problems


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Correct-Horse-9")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "Correct-Horse-9")
    assert not verify_password(hashed, "correct-horse-9")
    assert not verify_password(None, "anything")
    assert not verify_password("not-a-hash", "anything")


def test_opaque_tokens_are_random_and_hashed() -> None:
    a, b = new_opaque_token(), new_opaque_token()
    assert a != b and len(a) >= 43
    assert hash_token(a) != a and len(hash_token(a)) == 64


def test_access_token_roundtrip() -> None:
    user_id, session_id = uuid.uuid4(), uuid.uuid4()
    token, _ = create_access_token(user_id, session_id)
    claims = decode_access_token(token)
    assert (claims.user_id, claims.session_id) == (user_id, session_id)
    with pytest.raises(TokenError):
        decode_access_token(token + "x")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("07701234567", "+9647701234567"),
        ("0780-123-4567", "+9647801234567"),
        ("+964 750 123 4567", "+9647501234567"),
        ("00964 790 123 4567", "+9647901234567"),
        ("٠٧٧٠١٢٣٤٥٦٧", "+9647701234567"),
    ],
)
def test_iraqi_phone_normalization(raw: str, expected: str) -> None:
    assert normalize_iraqi_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "07201234567", "+9617701234567", "0770123456"])
def test_invalid_phones(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_iraqi_phone(raw)


def test_password_policy() -> None:
    assert password_problems("Correct-Horse-9") == []
    assert "PASSWORD_TOO_SHORT" in password_problems("Ab1!")
    assert "PASSWORD_TOO_COMMON" in password_problems("password123")
    assert "PASSWORD_TOO_COMMON" in password_problems("aaaaaaaaaaaa")
    assert "PASSWORD_CONTAINS_EMAIL" in password_problems(
        "ali.hassan-2026", email="ali.hassan@x.iq"
    )


def _csrf_app() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/unsafe")
    def unsafe(request: Request) -> dict[str, bool]:
        enforce_csrf(request)
        return {"ok": True}

    return TestClient(app)


def test_csrf_double_submit() -> None:
    client = _csrf_app()
    client.cookies.set(CSRF_COOKIE, "abc123")
    assert client.post("/unsafe").status_code == 403
    assert client.post("/unsafe", headers={CSRF_HEADER: "wrong"}).status_code == 403
    assert client.post("/unsafe", headers={CSRF_HEADER: "abc123"}).status_code == 200


def test_rate_limiter_falls_back_to_memory_when_redis_is_down() -> None:
    limiter = RateLimiter("redis://127.0.0.1:1/0")  # nothing listens on port 1
    key = f"test:{uuid.uuid4()}"
    for _ in range(3):
        limiter.check(key, limit=3, window=60)
    with pytest.raises(RateLimitedError):
        limiter.check(key, limit=3, window=60)


def test_client_ip_trusts_only_configured_proxy_hops() -> None:
    from app.core.client_ip import resolve_client_ip

    chain = "6.6.6.6, 203.0.113.7"  # client-supplied value, then the edge proxy's entry
    assert resolve_client_ip("172.18.0.5", chain, 0) == "172.18.0.5"  # header ignored
    assert resolve_client_ip("172.18.0.5", chain, 1) == "203.0.113.7"
    assert resolve_client_ip("172.18.0.5", chain, 2) == "6.6.6.6"
    assert resolve_client_ip("172.18.0.5", "203.0.113.7", 2) == "172.18.0.5"  # too short
    assert resolve_client_ip("172.18.0.5", "not-an-ip", 1) == "172.18.0.5"
    assert resolve_client_ip("172.18.0.5", None, 1) == "172.18.0.5"
    assert resolve_client_ip(None, " 2001:db8::1 ", 1) == "2001:db8::1"
