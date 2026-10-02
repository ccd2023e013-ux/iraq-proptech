"""Agency use cases."""

from __future__ import annotations

import contextlib
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agencies.models import (
    Agency,
    AgencyInvitation,
    AgencyMember,
    AgencyStatus,
    AgentProfile,
    MemberRole,
)
from app.agencies.schemas import AgencyIn, AgencyUpdate, AgentProfileIn
from app.audit import service as audit
from app.auth.deps import Principal
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.notifications.email import EmailMessage, get_email_provider
from app.policies import can_manage_agency, membership
from app.rbac.catalog import Role
from app.users.models import User, UserRole
from app.users.validation import normalize_email

INVITATION_TTL = timedelta(days=14)


def _now() -> datetime:
    return datetime.now(UTC)


def slugify(text: str) -> str:
    """ASCII slug; Arabic-only names fall back to a short random slug."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:60]
    return slug or "agency"


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    while db.execute(select(Agency.id).where(Agency.slug == slug)).first() is not None:
        slug = f"{base}-{uuid.uuid4().hex[:6]}"
    return slug


def grant_system_role(db: Session, user: User, role: Role, *, reason: str) -> None:
    """Role granted as a consequence of a user's own verified action (not by an admin)."""
    if role in user.roles:
        return
    user.role_links.append(UserRole(role_code=role.value, granted_by_id=None))
    audit.record(
        db,
        "user.role_granted_system",
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        data={"role": role.value, "reason": reason},
    )


def get_agency_or_404(db: Session, agency_id: uuid.UUID) -> Agency:
    agency = db.get(Agency, agency_id)
    if agency is None:
        raise NotFoundError("Agency not found", code="AGENCY_NOT_FOUND")
    return agency


def create_agency(db: Session, principal: Principal, data: AgencyIn) -> Agency:
    if membership(db, principal.id) is not None:
        raise ConflictError("You already belong to an agency", code="ALREADY_AGENCY_MEMBER")
    agency = Agency(
        **data.model_dump(mode="json", exclude={"city_id"}),
        city_id=data.city_id,
        slug=_unique_slug(db, slugify(data.name_en or data.name_ar)),
        status=AgencyStatus.PENDING_VERIFICATION,
        created_by_id=principal.id,
    )
    agency.members.append(AgencyMember(user_id=principal.id, role=MemberRole.OWNER))
    db.add(agency)
    db.flush()
    grant_system_role(db, principal.user, Role.AGENCY_OWNER, reason=f"agency:{agency.id}")
    audit.record(
        db, "agency.created", actor_id=principal.id, resource_type="agency", resource_id=agency.id
    )
    db.commit()
    return agency


def update_agency(db: Session, principal: Principal, agency: Agency, data: AgencyUpdate) -> Agency:
    if not can_manage_agency(db, principal, agency):
        raise PermissionDeniedError("You cannot edit this agency")
    changes = data.model_dump(mode="json", exclude_unset=True)
    if "city_id" in changes:
        changes["city_id"] = data.city_id
    for key, value in changes.items():
        setattr(agency, key, value)
    audit.record(
        db,
        "agency.updated",
        actor_id=principal.id,
        resource_type="agency",
        resource_id=agency.id,
        data={"fields": ",".join(sorted(changes))},
    )
    db.commit()
    return agency


def decide_agency(
    db: Session, principal: Principal, agency: Agency, decision: str, reason: str | None
) -> Agency:
    target = {
        "VERIFY": AgencyStatus.VERIFIED,
        "REJECT": AgencyStatus.REJECTED,
        "SUSPEND": AgencyStatus.SUSPENDED,
    }[decision]
    if target != AgencyStatus.VERIFIED and not reason:
        raise AppError("A reason is required", code="REASON_REQUIRED")
    m = membership(db, principal.id)
    if m is not None and m.agency_id == agency.id:
        raise PermissionDeniedError(
            "You cannot moderate your own agency", code="CONFLICT_OF_INTEREST"
        )
    previous = agency.status
    agency.status = target
    agency.status_reason = reason
    if target == AgencyStatus.VERIFIED:
        agency.verified_at = _now()
        agency.verified_by_id = principal.id
    audit.record(
        db,
        f"agency.{decision.lower()}",
        actor_id=principal.id,
        resource_type="agency",
        resource_id=agency.id,
        data={"from": previous, "to": target.value, "reason": reason},
    )
    db.commit()
    return agency


def list_agencies(
    db: Session, *, offset: int, limit: int, city_id: uuid.UUID | None, q: str | None
) -> tuple[list[Agency], int]:
    stmt = select(Agency).where(Agency.deleted_at.is_(None), Agency.status == AgencyStatus.VERIFIED)
    if city_id:
        stmt = stmt.where(Agency.city_id == city_id)
    if q:
        term = q.strip().lower()
        stmt = stmt.where(
            func.lower(Agency.name_ar).contains(term, autoescape=True)
            | func.lower(func.coalesce(Agency.name_en, "")).contains(term, autoescape=True)
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Agency.name_ar).offset(offset).limit(limit)).scalars()
    return list(rows), total


# --------------------------------------------------------------------------- members


def invite_agent(db: Session, principal: Principal, agency: Agency, email: str) -> AgencyInvitation:
    if not can_manage_agency(db, principal, agency):
        raise PermissionDeniedError("Only the agency owner can invite agents")
    if agency.status not in (AgencyStatus.VERIFIED, AgencyStatus.PENDING_VERIFICATION):
        raise AppError("This agency cannot invite agents now", code="AGENCY_INACTIVE")
    email = normalize_email(email)
    invitation = AgencyInvitation(
        agency_id=agency.id,
        email=email,
        invited_by_id=principal.id,
        expires_at=_now() + INVITATION_TTL,
    )
    db.add(invitation)
    db.flush()
    audit.record(
        db,
        "agency.agent_invited",
        actor_id=principal.id,
        resource_type="agency",
        resource_id=agency.id,
        data={"invitation_id": str(invitation.id)},
    )
    db.commit()
    with contextlib.suppress(Exception):
        get_email_provider().send(
            EmailMessage(
                to=email,
                subject=f"دعوة للانضمام إلى {agency.name_ar} / Agency invitation",
                text=(
                    f"تمت دعوتك للانضمام إلى المكتب العقاري «{agency.name_ar}» كوكيل.\n"
                    "سجّل الدخول بهذا البريد ثم افتح لوحة التحكم لقبول الدعوة.\n\n"
                    f"You were invited to join “{agency.name_en or agency.name_ar}” as an agent. "
                    "Sign in with this email and accept the invitation from your dashboard."
                ),
                tags=("agency_invitation",),
            )
        )
    return invitation


def pending_invitations(db: Session, user: User) -> list[AgencyInvitation]:
    return list(
        db.execute(
            select(AgencyInvitation)
            .where(
                AgencyInvitation.email == user.email,
                AgencyInvitation.accepted_at.is_(None),
                AgencyInvitation.revoked_at.is_(None),
                AgencyInvitation.expires_at > _now(),
            )
            .order_by(AgencyInvitation.created_at.desc())
        ).scalars()
    )


def accept_invitation(db: Session, principal: Principal, invitation_id: uuid.UUID) -> AgencyMember:
    invitation = db.get(AgencyInvitation, invitation_id, with_for_update=True)
    user = principal.user
    # Same error whether it does not exist or is addressed to someone else.
    if (
        invitation is None
        or invitation.email != user.email
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= _now()
    ):
        raise NotFoundError("Invitation not found", code="INVITATION_NOT_FOUND")
    if not user.email_verified:
        raise PermissionDeniedError("Verify your email first", code="EMAIL_NOT_VERIFIED")
    if membership(db, user.id) is not None:
        raise ConflictError("You already belong to an agency", code="ALREADY_AGENCY_MEMBER")
    agency = get_agency_or_404(db, invitation.agency_id)
    member = AgencyMember(agency_id=agency.id, user_id=user.id, role=MemberRole.AGENT)
    db.add(member)
    invitation.accepted_at = _now()
    grant_system_role(db, user, Role.AGENT, reason=f"agency:{agency.id}")
    audit.record(
        db,
        "agency.agent_joined",
        actor_id=user.id,
        resource_type="agency",
        resource_id=agency.id,
        data={"invitation_id": str(invitation.id)},
    )
    db.commit()
    return member


def list_members(
    db: Session, principal: Principal, agency: Agency
) -> list[tuple[AgencyMember, User]]:
    m = membership(db, principal.id)
    if not (can_manage_agency(db, principal, agency) or (m and m.agency_id == agency.id)):
        raise PermissionDeniedError("You cannot view this agency's members")
    rows = db.execute(
        select(AgencyMember, User)
        .join(User, User.id == AgencyMember.user_id)
        .where(AgencyMember.agency_id == agency.id)
        .order_by(AgencyMember.joined_at)
    ).all()
    return [(row[0], row[1]) for row in rows]


def remove_member(db: Session, principal: Principal, agency: Agency, user_id: uuid.UUID) -> None:
    if not can_manage_agency(db, principal, agency):
        raise PermissionDeniedError("Only the agency owner can remove agents")
    member = db.get(AgencyMember, (agency.id, user_id))
    if member is None:
        raise NotFoundError("Member not found")
    if member.role == MemberRole.OWNER:
        raise AppError("The agency owner cannot be removed", code="OWNER_REQUIRED")
    db.delete(member)
    audit.record(
        db,
        "agency.agent_removed",
        actor_id=principal.id,
        resource_type="agency",
        resource_id=agency.id,
        data={"user_id": str(user_id)},
    )
    db.commit()


# --------------------------------------------------------------------------- agent profiles


def upsert_agent_profile(db: Session, principal: Principal, data: AgentProfileIn) -> AgentProfile:
    profile = db.get(AgentProfile, principal.id)
    if profile is None:
        profile = AgentProfile(user_id=principal.id, **data.model_dump())
        db.add(profile)
    else:
        for key, value in data.model_dump().items():
            setattr(profile, key, value)
    audit.record(
        db,
        "agent.profile_updated",
        actor_id=principal.id,
        resource_type="user",
        resource_id=principal.id,
    )
    db.commit()
    return profile
