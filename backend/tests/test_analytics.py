"""Analytics: unique daily views, search statistics, scoped dashboards, privacy."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import service
from app.analytics.models import PropertyViewDaily, PropertyViewVisitor, SearchStatDaily
from app.rbac.catalog import Role
from tests.factories import auth_headers, make_listing, make_user
from tests.test_crm import make_agency

pytestmark = pytest.mark.db

INQUIRY = {"name": "زبون", "phone": "07701234567", "message": "هل العقار متاح للمعاينة؟"}


def _views(db: Session, property_id) -> int:
    db.expire_all()
    return int(
        db.execute(
            select(func.coalesce(func.sum(PropertyViewDaily.views), 0)).where(
                PropertyViewDaily.property_id == property_id
            )
        ).scalar_one()
    )


def test_views_are_unique_per_visitor_per_day_and_owners_not_counted(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    buyer = make_user(db_session)
    listing = make_listing(db_session, owner)
    url = f"/api/v1/analytics/property-views/{listing.id}"

    for _ in range(3):  # anonymous, same client → one view
        assert api.post(url, headers={"User-Agent": "UA-1"}).status_code == 204
    assert _views(db_session, listing.id) == 1
    api.post(url, headers={"User-Agent": "UA-2"})  # different anonymous browser
    assert _views(db_session, listing.id) == 2

    buyer_h = auth_headers(api, buyer)
    api.post(url, headers=buyer_h)
    api.post(url, headers=buyer_h)
    assert _views(db_session, listing.id) == 3

    api.post(url, headers=auth_headers(api, owner))  # owner's own views are ignored
    assert _views(db_session, listing.id) == 3

    # No raw identifiers are stored: only salted hashes.
    hashes = list(db_session.execute(select(PropertyViewVisitor.visitor_hash)).scalars())
    assert hashes and all(len(h) == 64 and str(buyer.id) not in h for h in hashes)


def test_views_ignored_for_unpublished_listing(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    draft = make_listing(db_session, owner, status="PENDING_REVIEW")
    assert api.post(f"/api/v1/analytics/property-views/{draft.id}").status_code == 204
    assert _views(db_session, draft.id) == 0


def test_visitor_hash_rotates_daily() -> None:
    today = service.today()
    assert service._visitor_hash(today, "u:1") == service._visitor_hash(today, "u:1")
    assert service._visitor_hash(today, "u:1") != service._visitor_hash(
        today - timedelta(days=1), "u:1"
    )


def test_purge_removes_old_visitor_keys(db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    listing = make_listing(db_session, owner)
    old = service.today() - timedelta(days=service.VISITOR_RETENTION_DAYS + 1)
    db_session.add(PropertyViewVisitor(day=old, property_id=listing.id, visitor_hash="x" * 64))
    db_session.add(
        PropertyViewVisitor(day=service.today(), property_id=listing.id, visitor_hash="y" * 64)
    )
    db_session.commit()
    assert service.purge_visitors(db_session)["purged"] == 1
    remaining = list(db_session.execute(select(PropertyViewVisitor.visitor_hash)).scalars())
    assert remaining == ["y" * 64]


def test_search_statistics_are_aggregated_without_query_text(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    make_listing(db_session, owner, title_ar="بيت للبيع في البصرة")
    assert api.get("/api/v1/search/properties?q=بيت&purpose=SALE").json()["total"] == 1
    api.get("/api/v1/search/properties?q=zzzz-no-match-zzzz&purpose=SALE")
    api.get("/api/v1/search/properties?purpose=SALE&page=2")  # later pages are not counted
    db_session.expire_all()
    rows = list(db_session.execute(select(SearchStatDaily)).scalars())
    assert len(rows) == 1
    assert rows[0].purpose == "SALE" and rows[0].governorate_id == ""
    assert rows[0].searches == 2 and rows[0].zero_results == 1
    columns = set(SearchStatDaily.__table__.columns.keys())
    assert "q" not in columns and "query" not in columns


def test_my_dashboard_counts_views_favorites_inquiries_and_leads(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    buyer = make_user(db_session)
    mine = make_listing(db_session, owner, title_ar="بيتي")
    other = make_listing(db_session, make_user(db_session, roles=[Role.PROPERTY_OWNER]))
    demo = make_listing(db_session, owner, is_demo=True)
    buyer_h = auth_headers(api, buyer)
    for prop in (mine, other, demo):
        api.post(f"/api/v1/analytics/property-views/{prop.id}", headers=buyer_h)
    assert api.put(f"/api/v1/properties/{mine.id}/favorite", headers=buyer_h).status_code == 204
    assert (
        api.post(
            f"/api/v1/properties/{mine.id}/inquiries", headers=buyer_h, json=INQUIRY
        ).status_code
        == 201
    )

    body = api.get("/api/v1/analytics/overview", headers=auth_headers(api, owner)).json()
    s = body["summary"]
    assert s["views"] == 1  # other's listing and the demo listing are excluded
    assert s["inquiries"] == 1 and s["leads"] == 1
    assert s["inquiry_rate"] == 1.0
    assert s["favorites"] == 1
    assert s["listings_active"] == 1
    assert body["top_listings"][0]["title_ar"] == "بيتي"
    assert body["top_listings"][0]["inquiries"] == 1
    assert len(body["series"]) == 30
    assert sum(d["views"] for d in body["series"]) == 1
    assert "agents" not in body and "platform" not in body

    with_demo = api.get(
        "/api/v1/analytics/overview?include_demo=true", headers=auth_headers(api, owner)
    ).json()
    assert with_demo["summary"]["views"] == 2


def test_customer_cannot_see_dashboards(api: TestClient, db_session: Session) -> None:
    buyer_h = auth_headers(api, make_user(db_session))
    assert api.get("/api/v1/analytics/overview", headers=buyer_h).status_code == 403
    assert api.get("/api/v1/analytics/overview?scope=platform", headers=buyer_h).status_code == 403
    assert api.get("/api/v1/analytics/overview").status_code == 401


def test_agency_dashboard_scoped_to_owner_with_agent_activity(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.AGENCY_OWNER])
    agent = make_user(db_session, roles=[Role.AGENT])
    agency = make_agency(db_session, owner, [agent])
    other_owner = make_user(db_session, roles=[Role.AGENCY_OWNER])
    other_agency = make_agency(db_session, other_owner)
    listing = make_listing(db_session, agent, agency_id=agency.id, agent_id=agent.id)
    buyer_h = auth_headers(api, make_user(db_session))
    api.post(f"/api/v1/properties/{listing.id}/inquiries", headers=buyer_h, json=INQUIRY)

    owner_h = auth_headers(api, owner)
    body = api.get("/api/v1/analytics/overview?scope=agency", headers=owner_h).json()
    assert body["summary"]["leads"] == 1
    agents = {a["user_id"]: a for a in body["agents"]}
    assert agents[str(agent.id)]["leads_assigned"] == 1

    # Another agency's owner, and an agent of this agency, cannot read it (404, no leak).
    assert (
        api.get(
            f"/api/v1/analytics/overview?scope=agency&agency_id={agency.id}",
            headers=auth_headers(api, other_owner),
        ).status_code
        == 404
    )
    assert (
        api.get(
            f"/api/v1/analytics/overview?scope=agency&agency_id={agency.id}",
            headers=auth_headers(api, agent),
        ).status_code
        == 404
    )
    assert other_agency.id != agency.id


def test_platform_dashboard_for_admins(api: TestClient, db_session: Session) -> None:
    admin = make_user(db_session, roles=[Role.ADMIN])
    api.get("/api/v1/search/properties?purpose=RENT&rent_period=MONTHLY")
    body = api.get(
        "/api/v1/analytics/overview?scope=platform", headers=auth_headers(api, admin)
    ).json()
    assert body["platform"]["searches"] >= 1
    assert body["platform"]["searches_by_purpose"].get("RENT", 0) >= 1
    assert body["platform"]["new_users"] >= 1
    assert "views = unique visitors per listing per day (local time)" in body["data_notes"]


def test_date_range_validation(api: TestClient, db_session: Session) -> None:
    h = auth_headers(api, make_user(db_session, roles=[Role.PROPERTY_OWNER]))
    bad = api.get("/api/v1/analytics/overview?date_from=2026-05-02&date_to=2026-05-01", headers=h)
    assert bad.status_code == 400
    too_long = api.get(
        "/api/v1/analytics/overview?date_from=2024-01-01&date_to=2026-01-01", headers=h
    )
    assert too_long.status_code == 400
    ok = api.get("/api/v1/analytics/overview?date_from=2026-05-01&date_to=2026-05-07", headers=h)
    assert ok.status_code == 200 and len(ok.json()["series"]) == 7


def test_property_analytics_only_for_managers(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    stranger = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    listing = make_listing(db_session, owner)
    api.post(f"/api/v1/analytics/property-views/{listing.id}", headers={"User-Agent": "x"})
    url = f"/api/v1/analytics/properties/{listing.id}"
    mine = api.get(url, headers=auth_headers(api, owner))
    assert mine.status_code == 200 and mine.json()["summary"]["views"] == 1
    assert api.get(url, headers=auth_headers(api, stranger)).status_code == 404
