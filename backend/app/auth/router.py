"""/api/v1/auth — registration, sign-in, tokens, verification, passwords."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.cookies import REFRESH_COOKIE, clear_auth_cookies, enforce_csrf, set_auth_cookies
from app.auth.deps import Principal, get_principal
from app.auth.models import AuthSession
from app.auth.schemas import (
    AuthOut,
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    MeOut,
    MessageOut,
    RefreshIn,
    RegisterIn,
    RegisterOut,
    ResetPasswordIn,
    SessionOut,
    TokenIn,
    user_out,
)
from app.core.errors import AuthenticationError, NotFoundError, error_body
from app.core.rate_limit import limit_identifier, rate_limit
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

TRANSPORT_HEADER = "X-Auth-Transport"


def _wants_bearer(request: Request) -> bool:
    return request.headers.get(TRANSPORT_HEADER, "").lower() == "bearer"


def _auth_response(request: Request, response: Response, issued: service.IssuedTokens) -> AuthOut:
    out = AuthOut(user=user_out(issued.user), access_expires_at=issued.access_expires_at)
    if _wants_bearer(request):
        out.access_token = issued.access_token
        out.refresh_token = issued.refresh_token
    else:
        set_auth_cookies(
            response,
            access_token=issued.access_token,
            access_expires_at=issued.access_expires_at,
            refresh_token=issued.refresh_token,
            refresh_expires_at=issued.refresh_expires_at,
        )
    return out


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", limit=10, window=3600))],
)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    user = service.register_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone=body.phone,
        account_type=body.account_type,
        locale=body.locale,
    )
    return RegisterOut(user=user_out(user), verification_required=True)


@router.post(
    "/login",
    response_model=AuthOut,
    dependencies=[Depends(rate_limit("login", limit=20, window=300))],
)
def login(
    body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> AuthOut:
    limit_identifier("login", body.email, limit=10, window=900)
    user = service.authenticate(db, body.email, body.password)
    issued = service.start_session(db, user)
    return _auth_response(request, response, issued)


@router.post(
    "/refresh",
    response_model=AuthOut,
    dependencies=[Depends(rate_limit("refresh", limit=60, window=300))],
)
def refresh(
    request: Request,
    response: Response,
    body: RefreshIn | None = None,
    db: Session = Depends(get_db),
) -> AuthOut | JSONResponse:
    token = body.refresh_token if body and body.refresh_token else None
    if token is None:
        token = request.cookies.get(REFRESH_COOKIE)
        if token is None:
            raise AuthenticationError("No refresh token", code="REFRESH_TOKEN_INVALID")
        enforce_csrf(request)
    try:
        issued = service.refresh_session(db, token)
    except AuthenticationError as exc:
        # Return (not raise) so the stale cookies are cleared on this response.
        failed = JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message)
        )
        clear_auth_cookies(failed)
        return failed
    return _auth_response(request, response, issued)


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    response: Response,
    body: RefreshIn | None = None,
    db: Session = Depends(get_db),
) -> MessageOut:
    """Ends the current session. Idempotent and safe to call when signed out."""
    token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if token is not None:
        if body is None or not body.refresh_token:
            enforce_csrf(request)
        session = service.session_for_refresh_token(db, token)
        if session is not None:
            service.revoke_session(db, session, reason="logout", actor_id=session.user_id)
    clear_auth_cookies(response)
    return MessageOut(message="Signed out")


@router.post("/logout-all", response_model=MessageOut)
def logout_all(
    response: Response,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MessageOut:
    service.revoke_all_sessions(db, principal.id, reason="logout_all", actor_id=principal.id)
    db.commit()
    clear_auth_cookies(response)
    return MessageOut(message="Signed out everywhere")


@router.get("/capabilities")
def capabilities() -> dict[str, bool]:
    """What the sign-up flow can promise: is email (verification, reset) delivered?"""
    from app.core.config import get_settings

    settings = get_settings()
    return {"email_delivery": settings.email_provider == "smtp" and bool(settings.smtp_host)}


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)) -> MeOut:
    return MeOut(
        user=user_out(principal.user), permissions=sorted(p.value for p in principal.permissions)
    )


@router.post(
    "/verify-email",
    response_model=MessageOut,
    dependencies=[Depends(rate_limit("verify", limit=30, window=3600))],
)
def verify_email(body: TokenIn, db: Session = Depends(get_db)) -> MessageOut:
    service.verify_email(db, body.token)
    return MessageOut(message="Email verified")


@router.post(
    "/resend-verification",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("resend", limit=5, window=3600))],
)
def resend_verification(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> MessageOut:
    service.resend_verification(db, principal.user)
    return MessageOut(message="If verification is pending, a new email was sent")


@router.post(
    "/password/forgot",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot", limit=10, window=3600))],
)
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)) -> MessageOut:
    limit_identifier("forgot", body.email, limit=3, window=3600)
    service.request_password_reset(db, body.email)
    return MessageOut(message="If the account exists, a reset link was sent")


@router.post(
    "/password/reset",
    response_model=MessageOut,
    dependencies=[Depends(rate_limit("reset", limit=20, window=3600))],
)
def reset_password(
    body: ResetPasswordIn, response: Response, db: Session = Depends(get_db)
) -> MessageOut:
    service.reset_password(db, body.token, body.new_password)
    clear_auth_cookies(response)
    return MessageOut(message="Password updated. Please sign in.")


@router.post("/password/change", response_model=MessageOut)
def change_password(
    body: ChangePasswordIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MessageOut:
    service.change_password(
        db,
        principal.user,
        current_password=body.current_password,
        new_password=body.new_password,
        session_id=principal.session.id,
    )
    return MessageOut(message="Password changed. Other sessions were signed out.")


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[SessionOut]:
    rows = db.execute(
        select(AuthSession)
        .where(AuthSession.user_id == principal.id, AuthSession.revoked_at.is_(None))
        .order_by(AuthSession.last_used_at.desc())
    ).scalars()
    return [
        SessionOut.model_validate(row).model_copy(
            update={"current": row.id == principal.session.id}
        )
        for row in rows
    ]


@router.delete("/sessions/{session_id}", response_model=MessageOut)
def revoke_session(
    session_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MessageOut:
    session = db.get(AuthSession, session_id)
    # Same 404 for "not yours" and "does not exist": no session IDs leak.
    if session is None or session.user_id != principal.id:
        raise NotFoundError("Session not found")
    service.revoke_session(db, session, reason="user_revoked", actor_id=principal.id)
    return MessageOut(message="Session revoked")
