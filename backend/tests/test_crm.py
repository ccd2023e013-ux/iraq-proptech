"""CRM: inquiries → leads, pipeline, scoped authorization, activities, tasks,
appointments, customers, conversations, dashboard, events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import events
from app.agencies.models import Agency, AgencyMember, MemberRole
from app.audit.models import AuditLog
from app.crm.models import Conversation, Customer, Inquiry, Lead, LeadActivity
from app.db.session import get_engine
from app.rbac.catalog import Role
from tests.factories import auth_headers, make_listing, make_user

pytestmark = pytest.mark.db

INQUIRY = {
    "name": "سارة أحمد",
    "phone": "07701234567",
    "message": "هل العقار ما زال متاحاً؟ أرغب بالمعاينة.",
    "preferred_contact": "WHATSAPP",
}


def make_agency(db: Session, owner, agents=()) -> Agency:
    agency = Agency(
        name_ar="مكتب تجريبي",
        slug=f"agency-{uuid.uuid4().hex[:8]}",
        status="VERIFIED",
        created_by_id=owner.id,
    )
    db.add(agency)
    db.flush()
    db.add(AgencyMember(agency_id=agency.id, user_id=owner.id, role=MemberRole.OWNER))
    for agent in agents:
        db.add(AgencyMember(agency_id=agency.id, user_id=agent.id, role=MemberRole.AGENT))
    db.commit()
    return agency


@pytest.fixture
def world(api: TestClient, db_session: Session) -> dict[str, Any]:
    """An agency (owner + two agents), an independent owner, a customer, an admin."""
    owner = make_user(db_session, roles=[Role.AGENCY_OWNER], name="صاحب المكتب")
    agent = make_user(db_session, roles=[Role.AGENT], name="الوكيل الأول")
    agent2 = make_user(db_session, roles=[Role.AGENT], name="الوكيل الثاني")
    outsider_agent = make_user(db_session, roles=[Role.AGENT], name="وكيل آخر")
    independent = make_user(db_session, roles=[Role.PROPERTY_OWNER], name="مالك مستقل")
    customer = make_user(db_session, name="زبون")
    admin = make_user(db_session, roles=[Role.ADMIN])
    agency = make_agency(db_session, owner, [agent, agent2])
    other_owner = make_user(db_session, roles=[Role.AGENCY_OWNER])
    make_agency(db_session, other_owner, [outsider_agent])
    agency_listing = make_listing(db_session, agent, agency_id=agency.id, agent_id=agent.id)
    own_listing = make_listing(db_session, independent)
    return {
        "owner": owner,
        "agent": agent,
        "agent2": agent2,
        "outsider_agent": outsider_agent,
        "other_owner": other_owner,
        "independent": independent,
        "customer": customer,
        "admin": admin,
        "agency": agency,
        "agency_listing": agency_listing,
        "own_listing": own_listing,
        "h": {
            k: auth_headers(api, v)
            for k, v in {
                "owner": owner,
                "agent": agent,
                "agent2": agent2,
                "outsider_agent": outsider_agent,
                "other_owner": other_owner,
                "independent": independent,
                "customer": customer,
                "admin": admin,
            }.items()
        },
    }


def _inquire(api, headers, listing_id, **overrides) -> dict:
    response = api.post(
        f"/api/v1/properties/{listing_id}/inquiries", headers=headers, json={**INQUIRY, **overrides}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _lead_for(db: Session, inquiry_id: str) -> Lead:
    inquiry = db.get(Inquiry, uuid.UUID(inquiry_id))
    assert inquiry is not None and inquiry.lead_id is not None
    db.expire_all()
    lead = db.get(Lead, inquiry.lead_id)
    assert lead is not None
    return lead


# --------------------------------------------------------------------------- inquiries → leads


def test_inquiry_creates_agency_lead_assigned_to_listing_agent(
    api: TestClient, db_session: Session, world
) -> None:
    received: list[tuple[str, dict]] = []

    def handler(db, name, payload):
        received.append((name, payload))

    events.subscribe("*", handler)
    try:
        inquiry = _inquire(api, world["h"]["customer"], world["agency_listing"].id)
    finally:
        events.unsubscribe("*", handler)

    lead = _lead_for(db_session, inquiry["id"])
    assert lead.agency_id == world["agency"].id
    assert lead.assigned_to_id == world["agent"].id
    assert lead.status_code == "NEW" and lead.source == "INQUIRY"
    customer = db_session.get(Customer, lead.customer_id)
    assert customer.user_id == world["customer"].id
    assert customer.phone == "+9647701234567"  # normalized
    assert {name for name, _ in received} == {"inquiry.created", "lead.created"}
    assert db_session.execute(
        select(AuditLog).where(AuditLog.action == "inquiry.created")
    ).scalar_one()

    # the agent sees it, the agency owner sees it, the second agent does not
    for key in ("agent", "owner", "admin"):
        listed = api.get("/api/v1/crm/leads", headers=world["h"][key]).json()
        assert [i["id"] for i in listed["items"]] == [str(lead.id)], key
    for key in ("agent2", "outsider_agent", "other_owner", "independent"):
        assert api.get("/api/v1/crm/leads", headers=world["h"][key]).json()["total"] == 0, key
        assert api.get(f"/api/v1/crm/leads/{lead.id}", headers=world["h"][key]).status_code == 404
    # customers cannot read the CRM at all
    assert api.get("/api/v1/crm/leads", headers=world["h"]["customer"]).status_code == 403


def test_repeat_inquiry_reuses_open_lead_and_conversation(
    api: TestClient, db_session: Session, world
) -> None:
    first = _inquire(api, world["h"]["customer"], world["own_listing"].id)
    second = _inquire(api, world["h"]["customer"], world["own_listing"].id, message="سؤال ثانٍ مهم")
    assert _lead_for(db_session, first["id"]).id == _lead_for(db_session, second["id"]).id
    lead = _lead_for(db_session, first["id"])
    assert lead.agency_id is None and lead.owner_user_id == world["independent"].id
    kinds = (
        db_session.execute(select(LeadActivity.kind).where(LeadActivity.lead_id == lead.id))
        .scalars()
        .all()
    )
    assert kinds.count("INQUIRY") == 2
    convs = (
        db_session.execute(
            select(Conversation).where(Conversation.customer_user_id == world["customer"].id)
        )
        .scalars()
        .all()
    )
    assert len(convs) == 1


def test_inquiry_rules(api: TestClient, db_session: Session, world) -> None:
    url = f"/api/v1/properties/{world['own_listing'].id}/inquiries"
    own = api.post(url, headers=world["h"]["independent"], json=INQUIRY)
    assert own.status_code == 422 and own.json()["error"]["code"] == "OWN_LISTING"
    no_contact = {**INQUIRY, "phone": None}
    assert api.post(url, headers=world["h"]["customer"], json=no_contact).status_code == 422
    assert api.post(url, json=INQUIRY).status_code == 401
    unverified = make_user(db_session, verified=False)
    response = api.post(url, headers=auth_headers(api, unverified), json=INQUIRY)
    assert response.status_code == 403 and response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    draft = make_listing(db_session, world["independent"], status="DRAFT")
    hidden = api.post(
        f"/api/v1/properties/{draft.id}/inquiries", headers=world["h"]["customer"], json=INQUIRY
    )
    assert hidden.status_code == 404


def test_my_inquiries_shows_only_own_messages(api: TestClient, db_session: Session, world) -> None:
    _inquire(api, world["h"]["customer"], world["own_listing"].id)
    mine = api.get("/api/v1/me/inquiries", headers=world["h"]["customer"]).json()
    assert mine["total"] == 1
    assert mine["items"][0]["property_reference"] == world["own_listing"].reference_code
    assert "lead_id" not in mine["items"][0]  # CRM internals are not exposed to customers
    assert api.get("/api/v1/me/inquiries", headers=world["h"]["agent"]).json()["total"] == 0


# --------------------------------------------------------------------------- pipeline


def test_pipeline_transitions_and_activity_timeline(
    api: TestClient, db_session: Session, world
) -> None:
    lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    h = world["h"]["agent"]
    url = f"/api/v1/crm/leads/{lead.id}"

    call = api.post(f"{url}/activities", headers=h, json={"kind": "CALL", "body": "اتصلت بالزبون"})
    assert call.status_code == 201
    assert api.get(url, headers=h).json()["status_code"] == "CONTACTED"  # auto-advanced

    assert (
        api.patch(url, headers=h, json={"status_code": "QUALIFIED"}).json()["status_code"]
        == "QUALIFIED"
    )
    lost = api.patch(url, headers=h, json={"status_code": "LOST"})
    assert lost.status_code == 422 and lost.json()["error"]["code"] == "LOST_REASON_REQUIRED"
    closed = api.patch(
        url, headers=h, json={"status_code": "LOST", "lost_reason": "السعر مرتفع"}
    ).json()
    assert closed["closed_at"] is not None and closed["lost_reason"] == "السعر مرتفع"
    reopened = api.patch(url, headers=h, json={"status_code": "NEGOTIATION"}).json()
    assert reopened["closed_at"] is None and reopened["lost_reason"] is None
    assert api.patch(url, headers=h, json={"status_code": "NOPE"}).status_code == 422

    timeline = api.get(f"{url}/activities", headers=h).json()
    kinds = [a["kind"] for a in timeline]
    assert kinds.count("STATUS_CHANGE") == 4 and "INQUIRY" in kinds and "CALL" in kinds
    system_kind = api.post(
        f"{url}/activities", headers=h, json={"kind": "STATUS_CHANGE", "body": "x"}
    )
    assert system_kind.status_code == 422
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert (
        api.post(
            f"{url}/activities",
            headers=h,
            json={"kind": "NOTE", "body": "x", "occurred_at": future},
        ).status_code
        == 422
    )


def test_budget_requires_currency_and_is_never_converted(
    api: TestClient, db_session: Session, world
) -> None:
    lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    url = f"/api/v1/crm/leads/{lead.id}"
    h = world["h"]["agent"]
    assert api.patch(url, headers=h, json={"budget_max": "200000"}).status_code == 422
    ok = api.patch(url, headers=h, json={"budget_max": "200000", "budget_currency": "USD"}).json()
    assert ok["budget_max"] == "200000.00" and ok["budget_currency"] == "USD"
    assert api.patch(url, headers=h, json={"budget_min": "300000"}).status_code == 422  # > max


def test_assignment_rules(api: TestClient, db_session: Session, world) -> None:
    lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    url = f"/api/v1/crm/leads/{lead.id}"
    # agents cannot reassign
    assert (
        api.patch(
            url, headers=world["h"]["agent"], json={"assigned_to_id": str(world["agent2"].id)}
        ).status_code
        == 403
    )
    # owner cannot assign outside the agency
    outside = api.patch(
        url, headers=world["h"]["owner"], json={"assigned_to_id": str(world["outsider_agent"].id)}
    )
    assert outside.status_code == 422 and outside.json()["error"]["code"] == "INVALID_ASSIGNEE"
    moved = api.patch(
        url, headers=world["h"]["owner"], json={"assigned_to_id": str(world["agent2"].id)}
    )
    assert moved.status_code == 200 and moved.json()["assigned_to"]["id"] == str(world["agent2"].id)
    # the newly assigned agent now sees it; the listing's agent still owns it
    assert api.get(url, headers=world["h"]["agent2"]).status_code == 200
    assert api.get(url, headers=world["h"]["agent"]).status_code == 200
    # independent leads stay with their owner
    own_lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["own_listing"].id)["id"]
    )
    assert (
        api.patch(
            f"/api/v1/crm/leads/{own_lead.id}",
            headers=world["h"]["independent"],
            json={"assigned_to_id": str(world["agent"].id)},
        ).status_code
        == 403
    )


def test_manual_lead_and_customer_book(api: TestClient, db_session: Session, world) -> None:
    h = world["h"]["independent"]
    created = api.post(
        "/api/v1/crm/leads",
        headers=h,
        json={
            "customer": {"full_name": "علي حسن", "phone": "0780 123 4567"},
            "source": "WALK_IN",
            "property_id": str(world["own_listing"].id),
            "note": "زار المكتب",
            "budget_min": "100000000",
            "budget_currency": "IQD",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["customer"]["phone"] == "+9647801234567"
    assert body["source"] == "WALK_IN" and body["customer"]["is_platform_user"] is False
    customers = api.get("/api/v1/crm/customers", headers=h).json()
    assert [c["full_name"] for c in customers["items"]] == ["علي حسن"]
    cid = body["customer"]["id"]
    assert api.get(f"/api/v1/crm/customers/{cid}", headers=world["h"]["agent"]).status_code == 404
    patched = api.patch(
        f"/api/v1/crm/customers/{cid}", headers=h, json={"notes": "يفضل الاتصال مساءً"}
    )
    assert patched.json()["notes"] == "يفضل الاتصال مساءً"
    # a second lead for the same customer by id; someone else's listing is refused
    again = api.post("/api/v1/crm/leads", headers=h, json={"customer_id": cid, "source": "PHONE"})
    assert again.status_code == 201 and again.json()["customer"]["lead_count"] == 2
    foreign = api.post(
        "/api/v1/crm/leads",
        headers=h,
        json={"customer_id": cid, "property_id": str(world["agency_listing"].id)},
    )
    assert foreign.status_code == 404
    assert (
        api.post(
            "/api/v1/crm/leads", headers=world["h"]["agent"], json={"customer_id": cid}
        ).status_code
        == 404
    )
    assert api.post("/api/v1/crm/leads", headers=h, json={"source": "PHONE"}).status_code == 422
    assert (
        api.post(
            "/api/v1/crm/leads",
            headers=world["h"]["customer"],
            json={"customer": {"full_name": "x y"}},
        ).status_code
        == 403
    )


# --------------------------------------------------------------------------- tasks & appointments


def test_tasks_and_follow_ups(api: TestClient, db_session: Session, world) -> None:
    lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    h = world["h"]["agent"]
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    task = api.post(
        "/api/v1/crm/tasks",
        headers=h,
        json={"title": "معاودة الاتصال", "lead_id": str(lead.id), "due_at": yesterday},
    )
    assert task.status_code == 201 and task.json()["overdue"] is True
    tid = task.json()["id"]
    assert [
        t["id"]
        for t in api.get("/api/v1/crm/tasks", headers=h, params={"status": "overdue"}).json()[
            "items"
        ]
    ] == [tid]
    # the agency owner sees agency tasks; another agent does not
    assert (
        api.get("/api/v1/crm/tasks", headers=world["h"]["owner"], params={"status": "all"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        api.get("/api/v1/crm/tasks", headers=world["h"]["agent2"], params={"status": "all"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        api.patch(
            f"/api/v1/crm/tasks/{tid}", headers=world["h"]["agent2"], json={"completed": True}
        ).status_code
        == 404
    )
    # agents cannot hand tasks to colleagues; owners can
    assert (
        api.post(
            "/api/v1/crm/tasks",
            headers=h,
            json={
                "title": "مهمة",
                "lead_id": str(lead.id),
                "assigned_to_id": str(world["agent2"].id),
            },
        ).status_code
        == 403
    )
    delegated = api.post(
        "/api/v1/crm/tasks",
        headers=world["h"]["owner"],
        json={
            "title": "تحضير العقد",
            "lead_id": str(lead.id),
            "assigned_to_id": str(world["agent2"].id),
        },
    )
    assert delegated.status_code == 201
    done = api.patch(f"/api/v1/crm/tasks/{tid}", headers=h, json={"completed": True}).json()
    assert done["completed_at"] is not None and done["overdue"] is False

    follow = api.patch(
        f"/api/v1/crm/leads/{lead.id}", headers=h, json={"next_follow_up_at": yesterday}
    )
    assert follow.status_code == 200
    overdue = api.get("/api/v1/crm/leads", headers=h, params={"overdue": "true"}).json()
    assert overdue["total"] == 1


def test_appointments_advance_pipeline(api: TestClient, db_session: Session, world) -> None:
    lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    h = world["h"]["agent"]
    start = datetime.now(UTC) + timedelta(days=2)
    bad = api.post(
        f"/api/v1/crm/leads/{lead.id}/appointments",
        headers=h,
        json={"starts_at": start.isoformat(), "ends_at": (start - timedelta(hours=1)).isoformat()},
    )
    assert bad.status_code == 422
    appt = api.post(
        f"/api/v1/crm/leads/{lead.id}/appointments",
        headers=h,
        json={"starts_at": start.isoformat(), "location_text": "العشار"},
    )
    assert appt.status_code == 201
    assert appt.json()["property_id"] == str(world["agency_listing"].id)
    assert api.get(f"/api/v1/crm/leads/{lead.id}", headers=h).json()["status_code"] == "VIEWING"
    upcoming = api.get("/api/v1/crm/appointments", headers=world["h"]["owner"]).json()
    assert len(upcoming) == 1
    assert api.get("/api/v1/crm/appointments", headers=world["h"]["agent2"]).json() == []
    done = api.patch(
        f"/api/v1/crm/appointments/{appt.json()['id']}", headers=h, json={"status": "COMPLETED"}
    )
    assert done.json()["status"] == "COMPLETED"
    assert (
        api.patch(
            f"/api/v1/crm/appointments/{appt.json()['id']}",
            headers=world["h"]["agent2"],
            json={"status": "CANCELLED"},
        ).status_code
        == 404
    )


# --------------------------------------------------------------------------- conversations


def test_conversation_between_customer_and_agent(
    api: TestClient, db_session: Session, world
) -> None:
    _inquire(api, world["h"]["customer"], world["agency_listing"].id)
    mine = api.get("/api/v1/me/conversations", headers=world["h"]["customer"]).json()
    assert len(mine) == 1 and mine[0]["role"] == "customer" and mine[0]["lead_id"] is None
    conv_id = mine[0]["id"]

    agent_view = api.get("/api/v1/me/conversations", headers=world["h"]["agent"]).json()
    assert [c["id"] for c in agent_view] == [conv_id]
    assert agent_view[0]["unread"] == 1 and agent_view[0]["role"] == "lister"

    reply = api.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=world["h"]["agent"],
        json={"body": "نعم متاح، متى يناسبك؟"},
    )
    assert reply.status_code == 201
    messages = api.get(
        f"/api/v1/conversations/{conv_id}/messages", headers=world["h"]["customer"]
    ).json()
    assert [m["mine"] for m in messages] == [True, False]
    # reading marks the agent's reply as read
    assert (
        api.get("/api/v1/me/conversations", headers=world["h"]["customer"]).json()[0]["unread"] == 0
    )
    # the reply is on the lead's timeline
    lead_id = agent_view[0]["lead_id"]
    kinds = [
        a["kind"]
        for a in api.get(
            f"/api/v1/crm/leads/{lead_id}/activities", headers=world["h"]["agent"]
        ).json()
    ]
    assert "MESSAGE" in kinds
    # outsiders cannot read or post
    for key in ("agent2", "independent"):
        assert (
            api.get(
                f"/api/v1/conversations/{conv_id}/messages", headers=world["h"][key]
            ).status_code
            == 404
        )
        assert (
            api.post(
                f"/api/v1/conversations/{conv_id}/messages",
                headers=world["h"][key],
                json={"body": "x"},
            ).status_code
            == 404
        )


# --------------------------------------------------------------------------- statuses & dashboard


def test_status_configuration(api: TestClient, db_session: Session, world) -> None:
    admin = world["h"]["admin"]
    created = api.put(
        "/api/v1/admin/crm/statuses/documents",
        headers=admin,
        json={"name_ar": "تجهيز الأوراق", "name_en": "Paperwork", "sort_order": 45},
    )
    assert created.status_code == 200 and created.json()["code"] == "DOCUMENTS"
    codes = [s["code"] for s in api.get("/api/v1/crm/statuses", headers=world["h"]["agent"]).json()]
    assert codes.index("NEGOTIATION") < codes.index("DOCUMENTS") < codes.index("WON")
    locked = api.put(
        "/api/v1/admin/crm/statuses/WON",
        headers=admin,
        json={"name_ar": "x", "name_en": "x", "sort_order": 1, "is_active": False},
    )
    assert locked.status_code == 422
    assert (
        api.put(
            "/api/v1/admin/crm/statuses/DOCUMENTS",
            headers=world["h"]["owner"],
            json={"name_ar": "x", "name_en": "x", "sort_order": 1},
        ).status_code
        == 403
    )
    lead = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    api.patch(
        f"/api/v1/crm/leads/{lead.id}",
        headers=world["h"]["agent"],
        json={"status_code": "DOCUMENTS"},
    )
    in_use = api.put(
        "/api/v1/admin/crm/statuses/DOCUMENTS",
        headers=admin,
        json={"name_ar": "x", "name_en": "x", "sort_order": 45, "is_active": False},
    )
    assert in_use.status_code == 409


def test_dashboard_counts_are_scoped(api: TestClient, db_session: Session, world) -> None:
    a = _lead_for(
        db_session, _inquire(api, world["h"]["customer"], world["agency_listing"].id)["id"]
    )
    other_customer = make_user(db_session)
    b = _lead_for(
        db_session,
        _inquire(api, auth_headers(api, other_customer), world["agency_listing"].id)["id"],
    )
    _inquire(api, world["h"]["customer"], world["own_listing"].id)
    h = world["h"]["agent"]
    api.patch(f"/api/v1/crm/leads/{a.id}", headers=h, json={"status_code": "WON"})
    api.patch(
        f"/api/v1/crm/leads/{b.id}", headers=h, json={"status_code": "LOST", "lost_reason": "x"}
    )

    board = api.get("/api/v1/crm/dashboard", headers=world["h"]["owner"]).json()
    assert board["won"] == 1 and board["lost"] == 1 and board["conversion_rate"] == 0.5
    assert board["total_open"] == 0
    independent = api.get("/api/v1/crm/dashboard", headers=world["h"]["independent"]).json()
    assert independent["total_open"] == 1 and independent["won"] == 0
    assert independent["conversion_rate"] is None
    admin = api.get("/api/v1/crm/dashboard", headers=world["h"]["admin"]).json()
    assert admin["total_open"] == 1 and admin["won"] == 1


def test_lead_list_uses_constant_queries(api: TestClient, db_session: Session, world) -> None:
    for _ in range(6):
        customer = make_user(db_session)
        _inquire(api, auth_headers(api, customer), world["agency_listing"].id)
    statements: list[str] = []

    def count(*args: object, **kwargs: object) -> None:
        statements.append(str(args[2]))

    headers = world["h"]["owner"]
    engine = get_engine()
    sa_event.listen(engine, "before_cursor_execute", count)
    try:
        small = api.get("/api/v1/crm/leads", headers=headers, params={"page_size": 2})
        n_small = len(statements)
        statements.clear()
        large = api.get("/api/v1/crm/leads", headers=headers, params={"page_size": 6})
        n_large = len(statements)
    finally:
        sa_event.remove(engine, "before_cursor_execute", count)
    assert len(small.json()["items"]) == 2 and len(large.json()["items"]) == 6
    assert n_large == n_small  # no per-row queries


def test_failing_event_handler_does_not_break_inquiry(
    api: TestClient, db_session: Session, world
) -> None:
    def broken(db, name, payload):
        raise RuntimeError("boom")

    events.subscribe("lead.created", broken)
    try:
        inquiry = _inquire(api, world["h"]["customer"], world["own_listing"].id)
    finally:
        events.unsubscribe("lead.created", broken)
    assert _lead_for(db_session, inquiry["id"]).status_code == "NEW"
