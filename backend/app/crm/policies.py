"""Who may see and change CRM records.

Visibility of a lead:
* ``leads.read_any`` (ADMIN, SUPER_ADMIN): every lead;
* ``leads.read_agency`` and OWNER of the lead's agency: the agency's leads;
* ``leads.read_own``: leads the caller owns (accountable lister) or is
  assigned to.

Anything a caller cannot see is reported as 404, never 403, so lead IDs
cannot be probed. Changing a lead additionally requires ``leads.manage``;
(re)assignment is reserved to the agency owner (or admins).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import false, or_
from sqlalchemy.orm import Session

from app.agencies.models import MemberRole
from app.auth.deps import Principal
from app.crm.models import Customer, Lead
from app.policies import membership
from app.rbac.catalog import Permission


def owned_agency_id(db: Session, principal: Principal) -> uuid.UUID | None:
    m = membership(db, principal.id)
    return m.agency_id if m is not None and m.role == MemberRole.OWNER else None


def lead_scope(db: Session, principal: Principal) -> Any:
    """SQL condition selecting the leads ``principal`` may see."""
    if principal.has(Permission.LEADS_READ_ANY):
        return Lead.id.is_not(None)
    conditions: list[Any] = []
    if principal.has(Permission.LEADS_READ_OWN):
        conditions += [Lead.owner_user_id == principal.id, Lead.assigned_to_id == principal.id]
    if principal.has(Permission.LEADS_READ_AGENCY):
        agency_id = owned_agency_id(db, principal)
        if agency_id is not None:
            conditions.append(Lead.agency_id == agency_id)
    return or_(*conditions) if conditions else false()


def can_see_lead(db: Session, principal: Principal, lead: Lead) -> bool:
    if principal.has(Permission.LEADS_READ_ANY):
        return True
    if principal.has(Permission.LEADS_READ_OWN) and principal.id in (
        lead.owner_user_id,
        lead.assigned_to_id,
    ):
        return True
    if principal.has(Permission.LEADS_READ_AGENCY) and lead.agency_id is not None:
        return owned_agency_id(db, principal) == lead.agency_id
    return False


def can_manage_lead(db: Session, principal: Principal, lead: Lead) -> bool:
    return principal.has(Permission.LEADS_MANAGE) and can_see_lead(db, principal, lead)


def can_assign_lead(db: Session, principal: Principal, lead: Lead) -> bool:
    if not principal.has(Permission.LEADS_MANAGE):
        return False
    if principal.has(Permission.LEADS_READ_ANY):
        return True
    return lead.agency_id is not None and owned_agency_id(db, principal) == lead.agency_id


def customer_scope(db: Session, principal: Principal) -> Any:
    """Customers in the caller's own book (agency book for agency owners)."""
    if principal.has(Permission.LEADS_READ_ANY):
        return Customer.id.is_not(None)
    conditions: list[Any] = [Customer.owner_user_id == principal.id]
    agency_id = owned_agency_id(db, principal)
    if agency_id is not None:
        conditions.append(Customer.agency_id == agency_id)
    return or_(*conditions)
