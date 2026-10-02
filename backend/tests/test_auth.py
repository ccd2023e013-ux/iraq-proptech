"""Registration, verification, sign-in, token rotation and passwords (real DB)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import AuthSession
from app.core.config import get_settings
from app.notifications.email import MockEmailProvider
from app.users.models import User, UserStatus
from tests.factories import DEFAULT_PASSWORD, auth_headers, login, make_user, token_from_outbox

pytestmark = pytest.mark.db

REGISTER = "/api/v1/auth/register"
BEARER = {"X-Auth-Transport": "bearer"}


def _register(api: TestClient, **overrides: object) -> dict:
    payload = {
        "email": "Sara.Basri@Example.COM",
        "password": DEFAULT_PASSWORD,
        "full_name": "  سارة   البصري ",
        "locale": "ar",
    }
    payload.update(overrides)
    return {"response": api.post(REGISTER, json=payload), "payload": payload}


# --------------------------------------------------------------------------- registration


def test_register_creates_customer_and_sends_verification(
    api: TestClient, mock_outbox: MockEmailProvider
) -> None:
    response = _register(api)["response"]
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["verification_required"] is True
    user = body["user"]
    assert user["email"] == "sara.basri@example.com"  # normalized
    assert user["full_name"] == "سارة البصري"
    assert user["roles"] == ["CUSTOMER"]
    assert user["email_verified"] is False
    assert "password_hash" not in user
    message = mock_outbox.outbox()[-1]
    assert message.to == "sara.basri@example.com"
    assert "/verify-email?token=" in message.text


def test_register_property_owner(api: TestClient) -> None:
    response = _register(api, account_type="PROPERTY_OWNER")["response"]
    assert sorted(response.json()["user"]["roles"]) == ["CUSTOMER", "PROPERTY_OWNER"]


@pytest.mark.parametrize("role", ["ADMIN", "SUPER_ADMIN", "MODERATOR", "AGENT", "AGENCY_OWNER"])
def test_register_cannot_choose_privileged_role(api: TestClient, role: str) -> None:
    response = _register(api, account_type=role)["response"]
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_duplicate_email_is_case_insensitive(api: TestClient) -> None:
    assert _register(api)["response"].status_code == 201
    response = _register(api, email="SARA.BASRI@example.com")["response"]
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


def test_register_rejects_weak_password(api: TestClient) -> None:
    response = _register(api, password="1234567890")["response"]
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "WEAK_PASSWORD"
    assert "PASSWORD_TOO_COMMON" in error["details"]


def test_register_normalizes_iraqi_phone_and_rejects_duplicates(api: TestClient) -> None:
    first = _register(api, phone="0770 123 4567")["response"]
    assert first.json()["user"]["phone"] == "+9647701234567"
    second = _register(api, email="other@example.com", phone="+964 770 123 4567")["response"]
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PHONE_TAKEN"


def test_register_rejects_invalid_phone(api: TestClient) -> None:
    assert _register(api, phone="12345")["response"].status_code == 422


# --------------------------------------------------------------------------- verification


def test_email_verification_is_single_use(
    api: TestClient, mock_outbox: MockEmailProvider, db_session: Session
) -> None:
    _register(api)
    token = token_from_outbox(mock_outbox, "email_verify")
    ok = api.post("/api/v1/auth/verify-email", json={"token": token})
    assert ok.status_code == 200
    user = db_session.execute(
        select(User).where(User.email == "sara.basri@example.com")
    ).scalar_one()
    assert user.email_verified_at is not None

    again = api.post("/api/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "VERIFICATION_TOKEN_INVALID"


def test_verification_rejects_unknown_token(api: TestClient) -> None:
    response = api.post("/api/v1/auth/verify-email", json={"token": "x" * 43})
    assert response.json()["error"]["code"] == "VERIFICATION_TOKEN_INVALID"


def test_resend_invalidates_previous_link(
    api: TestClient, mock_outbox: MockEmailProvider, db_session: Session
) -> None:
    user = make_user(db_session, verified=False)
    headers = auth_headers(api, user)
    api.post("/api/v1/auth/resend-verification", headers=headers)
    first = token_from_outbox(mock_outbox, "email_verify")
    api.post("/api/v1/auth/resend-verification", headers=headers)
    second = token_from_outbox(mock_outbox, "email_verify")
    assert first != second
    assert api.post("/api/v1/auth/verify-email", json={"token": first}).status_code == 400
    assert api.post("/api/v1/auth/verify-email", json={"token": second}).status_code == 200


# --------------------------------------------------------------------------- login


def test_login_bearer_and_me(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    tokens = login(api, user.email.upper())  # email is case-insensitive
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["id"] == str(user.id)
    assert "inquiries.create" in body["permissions"]
    assert "users.read" not in body["permissions"]


def test_login_wrong_password_and_unknown_email_look_identical(
    api: TestClient, db_session: Session
) -> None:
    user = make_user(db_session)
    wrong = api.post("/api/v1/auth/login", json={"email": user.email, "password": "Wrong-pass-123"})
    unknown = api.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Wrong-pass-123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"
    failures = db_session.execute(
        select(AuditLog).where(AuditLog.action == "auth.login_failed")
    ).scalars()
    assert {f.actor_user_id for f in failures} >= {user.id, None}


def test_login_is_audited_with_request_context(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    login(api, user.email)
    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "auth.login", AuditLog.actor_user_id == user.id)
    ).scalar_one()
    assert entry.request_id
    assert entry.ip_address
    assert "password" not in str(entry.data).lower()


def test_unauthenticated_request_uses_error_envelope(api: TestClient) -> None:
    response = api.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_suspended_user_cannot_login_and_tokens_stop_working(
    api: TestClient, db_session: Session
) -> None:
    user = make_user(db_session)
    headers = auth_headers(api, user)
    user.status = UserStatus.SUSPENDED
    db_session.commit()  # (test transaction is still rolled back at the end)
    assert (
        api.get("/api/v1/auth/me", headers=headers).json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    )
    response = api.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- tokens


def test_refresh_rotates_and_detects_reuse(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    tokens = login(api, user.email)

    rotated = api.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh"]}, headers=BEARER
    )
    assert rotated.status_code == 200, rotated.text
    new = rotated.json()
    assert new["refresh_token"] != tokens["refresh"]

    # Replaying the consumed token = theft signal: whole session is revoked.
    replay = api.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh"]}, headers=BEARER
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"

    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"})
    assert me.json()["error"]["code"] == "SESSION_REVOKED"
    second = api.post(
        "/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}, headers=BEARER
    )
    assert second.status_code == 401


def test_logout_revokes_session(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    tokens = login(api, user.email)
    assert (
        api.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh"]}).status_code
        == 200
    )
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"})
    assert me.status_code == 401


def test_expired_access_token(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    login(api, user.email)
    session = db_session.execute(
        select(AuthSession).where(AuthSession.user_id == user.id)
    ).scalar_one()
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(session.id),
            "typ": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": past - timedelta(minutes=15),
            "exp": past,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.parametrize("attack", ["alg_none", "wrong_secret", "garbage", "refresh_as_access"])
def test_forged_tokens_are_rejected(api: TestClient, db_session: Session, attack: str) -> None:
    user = make_user(db_session)
    tokens = login(api, user.email)
    claims = jwt.decode(tokens["access"], options={"verify_signature": False})
    if attack == "alg_none":
        token = jwt.encode(claims, key=None, algorithm="none")  # type: ignore[arg-type]
    elif attack == "wrong_secret":
        token = jwt.encode(claims, "x" * 64, algorithm="HS256")
    elif attack == "garbage":
        token = "not.a.jwt"
    else:
        token = tokens["refresh"]
    response = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


# --------------------------------------------------------------------------- browser cookies + CSRF


def test_cookie_login_sets_httponly_cookies_and_requires_csrf(
    api: TestClient, db_session: Session
) -> None:
    user = make_user(db_session)
    response = api.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["access_token"] is None  # tokens never in the body for browsers
    set_cookie = response.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookie if c.startswith("access_token="))
    refresh_cookie = next(c for c in set_cookie if c.startswith("refresh_token="))
    csrf_cookie = next(c for c in set_cookie if c.startswith("csrf_token="))
    assert "HttpOnly" in access_cookie and "HttpOnly" in refresh_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "samesite=lax" in access_cookie.lower()

    # Safe request with cookie: allowed without CSRF header.
    assert api.get("/api/v1/auth/me").status_code == 200

    body = {"current_password": DEFAULT_PASSWORD, "new_password": "Another-Strong-Pass-7"}
    blocked = api.post("/api/v1/auth/password/change", json=body)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CSRF_FAILED"

    csrf = api.cookies.get("csrf_token")
    allowed = api.post("/api/v1/auth/password/change", json=body, headers={"X-CSRF-Token": csrf})
    assert allowed.status_code == 200, allowed.text


def test_cookie_refresh_rotates_cookies(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    api.post("/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    old_refresh = api.cookies.get("refresh_token")
    no_csrf = api.post("/api/v1/auth/refresh")
    assert no_csrf.status_code == 403
    rotated = api.post(
        "/api/v1/auth/refresh", headers={"X-CSRF-Token": api.cookies.get("csrf_token")}
    )
    assert rotated.status_code == 200
    assert api.cookies.get("refresh_token") != old_refresh


# --------------------------------------------------------------------------- passwords


def test_forgot_password_does_not_reveal_accounts(
    api: TestClient, mock_outbox: MockEmailProvider
) -> None:
    response = api.post("/api/v1/auth/password/forgot", json={"email": "ghost@example.com"})
    assert response.status_code == 202
    assert mock_outbox.outbox() == []


def test_password_reset_flow(
    api: TestClient, db_session: Session, mock_outbox: MockEmailProvider
) -> None:
    user = make_user(db_session)
    old = login(api, user.email)
    assert api.post("/api/v1/auth/password/forgot", json={"email": user.email}).status_code == 202
    token = token_from_outbox(mock_outbox, "password_reset")

    weak = api.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "short"})
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"
    # The rejected attempt was rolled back, so the link is still usable.
    new_password = "Brand-New-Secret-42"
    reset = api.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": new_password}
    )
    assert reset.status_code == 200, reset.text

    # Old sessions are gone, old password fails, new password works, link is single-use.
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old['access']}"})
    assert me.status_code == 401
    bad = api.post("/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    assert bad.status_code == 401
    login(api, user.email, new_password)
    again = api.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": "Other-Secret-42"}
    )
    assert again.status_code == 400


def test_change_password_keeps_current_session_only(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    other = login(api, user.email)
    current = login(api, user.email)
    headers = {"Authorization": f"Bearer {current['access']}"}
    response = api.post(
        "/api/v1/auth/password/change",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "Changed-Secret-55"},
        headers=headers,
    )
    assert response.status_code == 200
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 200
    stale = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other['access']}"})
    assert stale.status_code == 401


def test_change_password_requires_current_password(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    response = api.post(
        "/api/v1/auth/password/change",
        json={"current_password": "Not-the-password-1", "new_password": "Changed-Secret-55"},
        headers=auth_headers(api, user),
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- sessions


def test_cannot_revoke_someone_elses_session(api: TestClient, db_session: Session) -> None:
    alice = make_user(db_session)
    bob = make_user(db_session)
    login(api, bob.email)
    bob_session = db_session.execute(
        select(AuthSession).where(AuthSession.user_id == bob.id)
    ).scalar_one()
    response = api.delete(
        f"/api/v1/auth/sessions/{bob_session.id}", headers=auth_headers(api, alice)
    )
    assert response.status_code == 404


def test_list_sessions_marks_current(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    login(api, user.email)
    headers = auth_headers(api, user)
    sessions = api.get("/api/v1/auth/sessions", headers=headers).json()
    assert len(sessions) == 2
    assert sum(s["current"] for s in sessions) == 1
