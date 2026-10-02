"""Authentication use cases.

All functions take an open ``Session`` and commit at the end of a successful
use case, so each HTTP request is one atomic unit of work.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import events
from app.audit import service as audit
from app.auth.models import AuthSession, RefreshToken, TokenPurpose, VerificationToken
from app.auth.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    password_needs_rehash,
    verify_password,
)
from app.core.config import get_settings
from app.core.errors import AppError, AuthenticationError, ConflictError, PermissionDeniedError
from app.core.logging import client_ip_var, user_agent_var
from app.notifications.email import get_email_provider
from app.notifications.templates import password_reset_email, verification_email
from app.rbac.catalog import SELF_SERVICE_ROLES, Role
from app.users.models import User, UserRole, UserStatus
from app.users.validation import normalize_email, password_problems

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class WeakPasswordError(AppError):
    status_code = 422
    code = "WEAK_PASSWORD"


def ensure_password_acceptable(password: str, email: str | None) -> None:
    problems = password_problems(password, email=email)
    if problems:
        raise WeakPasswordError("Password does not meet the policy", details=problems)


# --------------------------------------------------------------------------- #
# Registration and verification
# --------------------------------------------------------------------------- #


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    phone: str | None,
    account_type: Role,
    locale: str,
) -> User:
    if account_type not in SELF_SERVICE_ROLES:
        raise PermissionDeniedError("This account type cannot be self-registered")
    email = normalize_email(email)
    ensure_password_acceptable(password, email)

    user = User(
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        preferred_locale=locale,
        status=UserStatus.ACTIVE,
        password_changed_at=_now(),
    )
    user.role_links.append(UserRole(role_code=Role.CUSTOMER))
    if account_type != Role.CUSTOMER:
        user.role_links.append(UserRole(role_code=account_type))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        diag = getattr(exc.orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None) or ""
        if "phone" in constraint:
            raise ConflictError("Phone number already registered", code="PHONE_TAKEN") from exc
        raise ConflictError("Email already registered", code="EMAIL_TAKEN") from exc

    audit.record(
        db,
        "auth.register",
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        data={"account_type": account_type.value},
    )
    token = _issue_token(db, user, TokenPurpose.EMAIL_VERIFY, user.email)
    events.emit(db, "user.registered", {"user_id": str(user.id)})
    db.commit()
    _send_verification(user, token)
    return user


def _issue_token(db: Session, user: User, purpose: TokenPurpose, target: str) -> str:
    settings = get_settings()
    ttl = (
        timedelta(minutes=settings.password_reset_ttl_minutes)
        if purpose == TokenPurpose.PASSWORD_RESET
        else timedelta(hours=settings.email_verification_ttl_hours)
    )
    # Only the newest token of a purpose stays valid.
    db.execute(
        update(VerificationToken)
        .where(
            VerificationToken.user_id == user.id,
            VerificationToken.purpose == purpose,
            VerificationToken.consumed_at.is_(None),
        )
        .values(consumed_at=_now())
    )
    token = new_opaque_token()
    db.add(
        VerificationToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token),
            target=target,
            expires_at=_now() + ttl,
        )
    )
    return token


def _send_verification(user: User, token: str) -> None:
    try:
        get_email_provider().send(
            verification_email(user.email, user.full_name, token, user.preferred_locale)
        )
    except Exception:
        # Delivery failure must not undo the registration; the user can resend.
        logger.exception("verification_email_failed", extra={"user_id": str(user.id)})


def resend_verification(db: Session, user: User) -> None:
    if user.email_verified:
        return
    token = _issue_token(db, user, TokenPurpose.EMAIL_VERIFY, user.email)
    db.commit()
    _send_verification(user, token)


def _consume_token(
    db: Session, token: str, purpose: TokenPurpose
) -> tuple[VerificationToken, User]:
    record = db.execute(
        select(VerificationToken)
        .where(VerificationToken.token_hash == hash_token(token))
        .with_for_update()
    ).scalar_one_or_none()
    invalid = AppError("Link is invalid or has expired", code="VERIFICATION_TOKEN_INVALID")
    if (
        record is None
        or record.purpose != purpose
        or record.consumed_at is not None
        or record.expires_at <= _now()
    ):
        raise invalid
    user = db.get(User, record.user_id)
    if user is None or user.deleted_at is not None:
        raise invalid
    record.consumed_at = _now()
    return record, user


def verify_email(db: Session, token: str) -> User:
    record, user = _consume_token(db, token, TokenPurpose.EMAIL_VERIFY)
    if record.target != user.email:
        raise AppError("Link is invalid or has expired", code="VERIFICATION_TOKEN_INVALID")
    user.email_verified_at = user.email_verified_at or _now()
    audit.record(
        db, "auth.email_verified", actor_id=user.id, resource_type="user", resource_id=user.id
    )
    db.commit()
    return user


# --------------------------------------------------------------------------- #
# Sessions and tokens
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IssuedTokens:
    user: User
    session: AuthSession
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(
        select(User).where(User.email == normalize_email(email), User.deleted_at.is_(None))
    ).scalar_one_or_none()
    # verify_password always hashes, so unknown emails take as long as wrong passwords.
    if not verify_password(user.password_hash if user else None, password) or user is None:
        audit.record(
            db,
            "auth.login_failed",
            actor_id=user.id if user else None,
            data={"reason": "invalid_credentials"},
        )
        db.commit()
        raise AuthenticationError("Invalid email or password", code="INVALID_CREDENTIALS")
    if user.status != UserStatus.ACTIVE:
        raise PermissionDeniedError("Account is not active", code="ACCOUNT_SUSPENDED")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def _new_refresh(db: Session, session: AuthSession) -> tuple[str, datetime]:
    token = new_opaque_token()
    expires_at = session.expires_at
    db.add(RefreshToken(session_id=session.id, token_hash=hash_token(token), expires_at=expires_at))
    return token, expires_at


def start_session(db: Session, user: User) -> IssuedTokens:
    now = _now()
    session = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        expires_at=now + timedelta(days=get_settings().jwt_refresh_ttl_days),
        user_agent=user_agent_var.get(),
        ip_address=client_ip_var.get(),
    )
    db.add(session)
    db.flush()
    refresh, refresh_exp = _new_refresh(db, session)
    access, access_exp = create_access_token(user.id, session.id)
    user.last_login_at = now
    audit.record(
        db, "auth.login", actor_id=user.id, resource_type="session", resource_id=session.id
    )
    db.commit()
    return IssuedTokens(user, session, access, access_exp, refresh, refresh_exp)


def refresh_session(db: Session, refresh_token: str) -> IssuedTokens:
    invalid = AuthenticationError(
        "Session expired, please sign in again", code="REFRESH_TOKEN_INVALID"
    )
    record = db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token))
        .with_for_update()  # serializes concurrent refreshes of the same token
    ).scalar_one_or_none()
    if record is None:
        raise invalid
    session = db.get(AuthSession, record.session_id, with_for_update=True)
    if session is None:
        raise invalid
    now = _now()
    if record.used_at is not None:
        # A consumed token was replayed: assume theft and kill the whole session.
        if session.revoked_at is None:
            session.revoked_at = now
            session.revoke_reason = "refresh_token_reuse"
            audit.record(
                db,
                "auth.refresh_token_reuse",
                actor_id=session.user_id,
                resource_type="session",
                resource_id=session.id,
            )
            db.commit()
        raise AuthenticationError("Session revoked", code="REFRESH_TOKEN_REUSED")
    user = db.get(User, session.user_id)
    if (
        session.revoked_at is not None
        or session.expires_at <= now
        or record.expires_at <= now
        or user is None
        or not user.is_active
    ):
        raise invalid

    record.used_at = now
    session.last_used_at = now
    new_refresh, refresh_exp = _new_refresh(db, session)
    access, access_exp = create_access_token(user.id, session.id)
    db.commit()
    return IssuedTokens(user, session, access, access_exp, new_refresh, refresh_exp)


def session_for_refresh_token(db: Session, refresh_token: str) -> AuthSession | None:
    record = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    ).scalar_one_or_none()
    return db.get(AuthSession, record.session_id) if record else None


def revoke_session(
    db: Session, session: AuthSession, *, reason: str, actor_id: uuid.UUID | None
) -> None:
    if session.revoked_at is None:
        session.revoked_at = _now()
        session.revoke_reason = reason
        audit.record(
            db,
            "auth.session_revoked",
            actor_id=actor_id,
            resource_type="session",
            resource_id=session.id,
            data={"reason": reason},
        )
    db.commit()


def revoke_all_sessions(
    db: Session,
    user_id: uuid.UUID,
    *,
    reason: str,
    actor_id: uuid.UUID | None,
    keep_session_id: uuid.UUID | None = None,
) -> int:
    stmt = (
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoke_reason=reason)
    )
    if keep_session_id is not None:
        stmt = stmt.where(AuthSession.id != keep_session_id)
    count = cast(CursorResult[Any], db.execute(stmt)).rowcount or 0
    audit.record(
        db,
        "auth.sessions_revoked",
        actor_id=actor_id,
        resource_type="user",
        resource_id=user_id,
        data={"reason": reason, "count": count},
    )
    return count


def resolve_access_token(db: Session, token: str) -> tuple[User, AuthSession]:
    try:
        claims = decode_access_token(token)
    except TokenError as exc:
        message = "Access token expired" if exc.code == "TOKEN_EXPIRED" else "Invalid access token"
        raise AuthenticationError(message, code=exc.code) from exc
    session = db.get(AuthSession, claims.session_id)
    if session is None or session.revoked_at is not None or session.user_id != claims.user_id:
        raise AuthenticationError("Session is no longer valid", code="SESSION_REVOKED")
    user = db.get(User, claims.user_id)
    if user is None or user.deleted_at is not None:
        raise AuthenticationError("Session is no longer valid", code="SESSION_REVOKED")
    if user.status != UserStatus.ACTIVE:
        raise PermissionDeniedError("Account is not active", code="ACCOUNT_SUSPENDED")
    return user, session


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #


def request_password_reset(db: Session, email: str) -> None:
    """Always succeeds from the caller's view, so it cannot reveal which emails exist."""
    user = db.execute(
        select(User).where(User.email == normalize_email(email), User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        return
    token = _issue_token(db, user, TokenPurpose.PASSWORD_RESET, user.email)
    audit.record(
        db,
        "auth.password_reset_requested",
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
    )
    db.commit()
    try:
        get_email_provider().send(
            password_reset_email(user.email, user.full_name, token, user.preferred_locale)
        )
    except Exception:
        logger.exception("password_reset_email_failed", extra={"user_id": str(user.id)})


def reset_password(db: Session, token: str, new_password: str) -> User:
    record, user = _consume_token(db, token, TokenPurpose.PASSWORD_RESET)
    ensure_password_acceptable(new_password, user.email)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    # Possession of the reset link proves control of the inbox.
    if record.target == user.email and user.email_verified_at is None:
        user.email_verified_at = _now()
    revoke_all_sessions(db, user.id, reason="password_reset", actor_id=user.id)
    audit.record(
        db, "auth.password_reset", actor_id=user.id, resource_type="user", resource_id=user.id
    )
    db.commit()
    return user


def change_password(
    db: Session, user: User, *, current_password: str, new_password: str, session_id: uuid.UUID
) -> None:
    if not verify_password(user.password_hash, current_password):
        raise AuthenticationError("Current password is incorrect", code="INVALID_CREDENTIALS")
    ensure_password_acceptable(new_password, user.email)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    revoke_all_sessions(
        db, user.id, reason="password_changed", actor_id=user.id, keep_session_id=session_id
    )
    audit.record(
        db, "auth.password_changed", actor_id=user.id, resource_type="user", resource_id=user.id
    )
    db.commit()
