"""/api/v1/agencies, /api/v1/agents, agency invitations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.agencies import service
from app.agencies.models import AgentProfile
from app.agencies.schemas import (
    AgencyDecisionIn,
    AgencyIn,
    AgencyOut,
    AgencyUpdate,
    AgentProfileIn,
    AgentProfileOut,
    InvitationIn,
    InvitationOut,
    MemberOut,
)
from app.auth.deps import (
    Principal,
    get_optional_principal,
    get_principal,
    require_permission,
    require_verified_email,
)
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.policies import can_view_agency, membership
from app.rbac.catalog import Permission

router = APIRouter(tags=["agencies"])


@router.post("/agencies", response_model=AgencyOut, status_code=status.HTTP_201_CREATED)
def create_agency(
    body: AgencyIn,
    principal: Principal = Depends(require_verified_email),
    _: Principal = Depends(require_permission(Permission.AGENCIES_CREATE)),
    db: Session = Depends(get_db),
) -> AgencyOut:
    return AgencyOut.model_validate(service.create_agency(db, principal, body))


@router.get("/agencies", response_model=Page[AgencyOut])
def list_agencies(
    city_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=100),
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
) -> Page[AgencyOut]:
    rows, total = service.list_agencies(
        db, offset=params.offset, limit=params.page_size, city_id=city_id, q=q
    )
    return Page(
        items=[AgencyOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/agencies/{agency_id}", response_model=AgencyOut)
def get_agency(
    agency_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AgencyOut:
    agency = service.get_agency_or_404(db, agency_id)
    if not can_view_agency(db, principal, agency):
        raise NotFoundError("Agency not found", code="AGENCY_NOT_FOUND")
    return AgencyOut.model_validate(agency)


@router.patch("/agencies/{agency_id}", response_model=AgencyOut)
def update_agency(
    agency_id: uuid.UUID,
    body: AgencyUpdate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> AgencyOut:
    agency = service.get_agency_or_404(db, agency_id)
    return AgencyOut.model_validate(service.update_agency(db, principal, agency, body))


@router.post("/agencies/{agency_id}/decision", response_model=AgencyOut)
def decide_agency(
    agency_id: uuid.UUID,
    body: AgencyDecisionIn,
    principal: Principal = Depends(require_permission(Permission.AGENCIES_VERIFY)),
    db: Session = Depends(get_db),
) -> AgencyOut:
    agency = service.get_agency_or_404(db, agency_id)
    return AgencyOut.model_validate(
        service.decide_agency(db, principal, agency, body.decision, body.reason)
    )


@router.get("/agencies/{agency_id}/members", response_model=list[MemberOut])
def list_members(
    agency_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    agency = service.get_agency_or_404(db, agency_id)
    return [
        MemberOut(
            user_id=m.user_id,
            full_name=u.full_name,
            role=m.role,
            title=m.title,
            joined_at=m.joined_at,
        )
        for m, u in service.list_members(db, principal, agency)
    ]


@router.delete("/agencies/{agency_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    agency_id: uuid.UUID,
    user_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    agency = service.get_agency_or_404(db, agency_id)
    service.remove_member(db, principal, agency, user_id)


@router.post(
    "/agencies/{agency_id}/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
def invite_agent(
    agency_id: uuid.UUID,
    body: InvitationIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> InvitationOut:
    agency = service.get_agency_or_404(db, agency_id)
    return InvitationOut.model_validate(service.invite_agent(db, principal, agency, body.email))


@router.get("/me/agency-invitations", response_model=list[InvitationOut])
def my_invitations(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[InvitationOut]:
    result = []
    for invitation in service.pending_invitations(db, principal.user):
        agency = service.get_agency_or_404(db, invitation.agency_id)
        out = InvitationOut.model_validate(invitation)
        out.agency_name = agency.name_ar
        result.append(out)
    return result


@router.post("/agency-invitations/{invitation_id}/accept", response_model=MemberOut)
def accept_invitation(
    invitation_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MemberOut:
    member = service.accept_invitation(db, principal, invitation_id)
    return MemberOut(
        user_id=member.user_id,
        full_name=principal.user.full_name,
        role=member.role,
        title=member.title,
        joined_at=member.joined_at,
    )


@router.get("/me/agency", response_model=AgencyOut | None)
def my_agency(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> AgencyOut | None:
    m = membership(db, principal.id)
    return AgencyOut.model_validate(service.get_agency_or_404(db, m.agency_id)) if m else None


@router.put("/agents/me", response_model=AgentProfileOut)
def upsert_agent_profile(
    body: AgentProfileIn,
    principal: Principal = Depends(require_permission(Permission.PROPERTIES_CREATE)),
    db: Session = Depends(get_db),
) -> AgentProfileOut:
    return AgentProfileOut.model_validate(service.upsert_agent_profile(db, principal, body))


@router.get("/agents/{user_id}", response_model=AgentProfileOut)
def get_agent_profile(user_id: uuid.UUID, db: Session = Depends(get_db)) -> AgentProfileOut:
    profile = db.get(AgentProfile, user_id)
    if profile is None:
        raise NotFoundError("Agent not found", code="AGENT_NOT_FOUND")
    out = AgentProfileOut.model_validate(profile)
    m = membership(db, user_id)
    if m is not None:
        agency = service.get_agency_or_404(db, m.agency_id)
        if agency.status == "VERIFIED" and agency.deleted_at is None:
            out.agency_id, out.agency_name = agency.id, agency.name_ar
    return out
