"""Agencies: creation, verification, invitations, membership-scoped access."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.notifications.email import MockEmailProvider
from app.rbac.catalog import Role
from app.users.models import User
from tests.factories import auth_headers, basra, listing_payload, make_user

pytestmark = pytest.mark.db

AGENCY = {
    "name_ar": "مكتب الفيحاء للعقارات",
    "name_en": "Al-Fayhaa Real Estate",
    "phone": "07701112233",
}


def _agency(api: TestClient, headers: dict[str, str]) -> dict:
    response = api.post("/api/v1/agencies", json=AGENCY, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_agency_grants_owner_role(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    headers = auth_headers(api, user)
    agency = _agency(api, headers)
    assert agency["status"] == "PENDING_VERIFICATION"
    assert agency["slug"] == "al-fayhaa-real-estate"
    assert agency["phone"] == "+9647701112233"
    me = api.get("/api/v1/auth/me", headers=headers).json()
    assert "AGENCY_OWNER" in me["user"]["roles"]
    again = api.post("/api/v1/agencies", json=AGENCY, headers=headers)
    assert again.json()["error"]["code"] == "ALREADY_AGENCY_MEMBER"


def test_unverified_email_cannot_create_agency(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session, verified=False)
    response = api.post("/api/v1/agencies", json=AGENCY, headers=auth_headers(api, user))
    assert response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_website_must_be_https(api: TestClient, db_session: Session) -> None:
    headers = auth_headers(api, make_user(db_session))
    response = api.post(
        "/api/v1/agencies", json={**AGENCY, "website": "http://example.com"}, headers=headers
    )
    assert response.status_code == 422


def test_agency_visible_publicly_only_after_verification(
    api: TestClient, db_session: Session
) -> None:
    owner_headers = auth_headers(api, make_user(db_session))
    agency = _agency(api, owner_headers)
    assert api.get(f"/api/v1/agencies/{agency['id']}").status_code == 404
    assert api.get(f"/api/v1/agencies/{agency['id']}", headers=owner_headers).status_code == 200
    assert api.get("/api/v1/agencies").json()["total"] == 0

    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    reject_without_reason = api.post(
        f"/api/v1/agencies/{agency['id']}/decision", json={"decision": "REJECT"}, headers=moderator
    )
    assert reject_without_reason.json()["error"]["code"] == "REASON_REQUIRED"
    verified = api.post(
        f"/api/v1/agencies/{agency['id']}/decision", json={"decision": "VERIFY"}, headers=moderator
    )
    assert verified.json()["status"] == "VERIFIED"
    assert api.get(f"/api/v1/agencies/{agency['id']}").status_code == 200
    found = api.get("/api/v1/agencies", params={"q": "fayhaa"}).json()
    assert [a["id"] for a in found["items"]] == [agency["id"]]


def test_owner_cannot_verify_own_agency(api: TestClient, db_session: Session) -> None:
    mod_owner = make_user(db_session, roles=[Role.MODERATOR])
    headers = auth_headers(api, mod_owner)
    agency = _agency(api, headers)
    response = api.post(
        f"/api/v1/agencies/{agency['id']}/decision", json={"decision": "VERIFY"}, headers=headers
    )
    assert response.json()["error"]["code"] == "CONFLICT_OF_INTEREST"


def test_invitation_flow_requires_consent(
    api: TestClient, db_session: Session, mock_outbox: MockEmailProvider
) -> None:
    owner_headers = auth_headers(api, make_user(db_session))
    agency = _agency(api, owner_headers)
    agent = make_user(db_session)
    intruder = make_user(db_session)

    invite = api.post(
        f"/api/v1/agencies/{agency['id']}/invitations",
        json={"email": agent.email},
        headers=owner_headers,
    )
    assert invite.status_code == 201
    assert any("agency_invitation" in m.tags for m in mock_outbox.outbox())

    # Not a member until the invitee accepts.
    members = api.get(f"/api/v1/agencies/{agency['id']}/members", headers=owner_headers).json()
    assert len(members) == 1

    stolen = api.post(
        f"/api/v1/agency-invitations/{invite.json()['id']}/accept",
        headers=auth_headers(api, intruder),
    )
    assert stolen.status_code == 404

    agent_headers = auth_headers(api, agent)
    pending = api.get("/api/v1/me/agency-invitations", headers=agent_headers).json()
    assert pending[0]["agency_name"] == AGENCY["name_ar"]
    accepted = api.post(
        f"/api/v1/agency-invitations/{invite.json()['id']}/accept", headers=agent_headers
    )
    assert accepted.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(User, agent.id)
    assert refreshed is not None and Role.AGENT in refreshed.roles
    assert api.get("/api/v1/me/agency", headers=agent_headers).json()["id"] == agency["id"]


def test_non_owner_cannot_invite_or_remove(api: TestClient, db_session: Session) -> None:
    owner_headers = auth_headers(api, make_user(db_session))
    agency = _agency(api, owner_headers)
    outsider = auth_headers(api, make_user(db_session))
    invite = api.post(
        f"/api/v1/agencies/{agency['id']}/invitations",
        json={"email": "x@example.com"},
        headers=outsider,
    )
    assert invite.status_code == 403
    owner_id = api.get("/api/v1/auth/me", headers=owner_headers).json()["user"]["id"]
    remove_owner = api.delete(
        f"/api/v1/agencies/{agency['id']}/members/{owner_id}", headers=owner_headers
    )
    assert remove_owner.json()["error"]["code"] == "OWNER_REQUIRED"


def _join(api: TestClient, db_session: Session, agency_id: str, owner_headers: dict) -> tuple:
    agent = make_user(db_session)
    invite = api.post(
        f"/api/v1/agencies/{agency_id}/invitations",
        json={"email": agent.email},
        headers=owner_headers,
    ).json()
    headers = auth_headers(api, agent)
    api.post(f"/api/v1/agency-invitations/{invite['id']}/accept", headers=headers)
    return agent, headers


def test_agency_listing_access_follows_membership(api: TestClient, db_session: Session) -> None:
    owner_headers = auth_headers(api, make_user(db_session))
    agency = _agency(api, owner_headers)
    agent, agent_headers = _join(api, db_session, agency["id"], owner_headers)
    gov, city = basra(db_session)

    listing = api.post("/api/v1/properties", json=listing_payload(gov, city), headers=agent_headers)
    assert listing.status_code == 201, listing.text
    body = listing.json()
    assert body["lister"]["kind"] == "agency"
    assert body["lister"]["agency_id"] == agency["id"]

    # The agency owner manages the agent's listing.
    owner_edit = api.patch(
        f"/api/v1/properties/{body['id']}",
        json={"title_ar": "عنوان من صاحب المكتب"},
        headers=owner_headers,
    )
    assert owner_edit.status_code == 200
    owner_list = api.get("/api/v1/me/properties", headers=owner_headers).json()
    assert body["id"] in [p["id"] for p in owner_list["items"]]

    # When the agent leaves, the listing stays with the agency and the agent loses access.
    removed = api.delete(
        f"/api/v1/agencies/{agency['id']}/members/{agent.id}", headers=owner_headers
    )
    assert removed.status_code == 204
    agent_edit = api.patch(
        f"/api/v1/properties/{body['id']}",
        json={"title_ar": "محاولة بعد المغادرة"},
        headers=agent_headers,
    )
    assert agent_edit.status_code == 404


def test_agent_profile_public(api: TestClient, db_session: Session) -> None:
    agent = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    headers = auth_headers(api, agent)
    saved = api.put(
        "/api/v1/agents/me",
        json={"display_name": "علي البصري", "public_phone": "07801234567", "years_experience": 7},
        headers=headers,
    )
    assert saved.status_code == 200
    public = api.get(f"/api/v1/agents/{agent.id}").json()
    assert public["public_phone"] == "+9647801234567"
    customer = auth_headers(api, make_user(db_session))
    assert (
        api.put("/api/v1/agents/me", json={"display_name": "x y"}, headers=customer).status_code
        == 403
    )
    users = db_session.execute(select(User).where(User.id == agent.id)).scalars()
    assert next(iter(users)).phone is None  # account phone untouched
