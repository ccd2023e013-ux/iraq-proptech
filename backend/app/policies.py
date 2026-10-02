"""Resource-level authorization rules for agencies and properties.

Permissions (RBAC) answer "may this kind of user do X at all"; these
functions answer "on *this* record". Keep every such rule here so it can be
reviewed and tested in one place.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agencies.models import Agency, AgencyMember, MemberRole
from app.auth.deps import Principal
from app.rbac.catalog import Permission


def membership(db: Session, user_id: uuid.UUID) -> AgencyMember | None:
    return db.execute(
        select(AgencyMember).where(AgencyMember.user_id == user_id)
    ).scalar_one_or_none()


def is_agency_owner(db: Session, user_id: uuid.UUID, agency_id: uuid.UUID) -> bool:
    m = membership(db, user_id)
    return m is not None and m.agency_id == agency_id and m.role == MemberRole.OWNER


def can_manage_agency(db: Session, principal: Principal, agency: Agency) -> bool:
    return principal.has(Permission.AGENCIES_MANAGE_ANY) or is_agency_owner(
        db, principal.id, agency.id
    )


def can_view_agency(db: Session, principal: Principal | None, agency: Agency) -> bool:
    if agency.deleted_at is not None:
        return principal is not None and principal.has(Permission.AGENCIES_MANAGE_ANY)
    if agency.status == "VERIFIED":
        return True
    if principal is None:
        return False
    if principal.has(Permission.AGENCIES_VERIFY) or principal.has(Permission.AGENCIES_MANAGE_ANY):
        return True
    m = membership(db, principal.id)
    return m is not None and m.agency_id == agency.id


def can_manage_property(
    db: Session,
    principal: Principal,
    *,
    lister_id: uuid.UUID,
    agency_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
) -> bool:
    """Who may edit a listing.

    * admins with ``properties.manage_any``;
    * for agency listings: the agency's owner, or the listing's creator / assigned
      agent *while they are still members of that agency* (an agent who leaves
      loses access; the listing stays with the agency);
    * for private listings: the lister.
    """
    if principal.has(Permission.PROPERTIES_MANAGE_ANY):
        return True
    if agency_id is not None:
        m = membership(db, principal.id)
        if m is None or m.agency_id != agency_id:
            return False
        return m.role == MemberRole.OWNER or principal.id in (lister_id, agent_id)
    return principal.id == lister_id


def can_view_private_property(
    db: Session,
    principal: Principal | None,
    *,
    lister_id: uuid.UUID,
    agency_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
) -> bool:
    """Unpublished listings, exact location, documents."""
    if principal is None:
        return False
    if principal.has(Permission.PROPERTIES_READ_PRIVATE):
        return True
    return can_manage_property(
        db, principal, lister_id=lister_id, agency_id=agency_id, agent_id=agent_id
    )
