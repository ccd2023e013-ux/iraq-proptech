"""Market Intelligence: typed statements, minimum samples, honest gaps, DEMO labelling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai import providers
from app.ai.providers import AIRequest, AIResponse
from app.market.intelligence import MarketStatement
from app.rbac.catalog import Role
from tests.factories import make_listing, make_user

REPORT = "/api/v1/market/report"


class InventingProvider:
    name = "inventing"
    model = "inventing-1"

    def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            data={"text": "Prices will rise 40% next year, guaranteed."},
            provider=self.name,
            model=self.model,
        )


@pytest.fixture(autouse=True)
def _reset_provider():
    yield
    providers.set_provider_override(None)


def test_statement_kind_is_bound_to_its_origin() -> None:
    MarketStatement(kind="FACT", origin="platform", section="supply", key="k", demo=False)
    with pytest.raises(ValidationError):
        MarketStatement(kind="FACT", origin="ai", section="supply", key="k", demo=False)
    with pytest.raises(ValidationError):  # AI can never produce an observed statistic
        MarketStatement(kind="OBSERVED", origin="ai", section="prices", key="k", demo=False)
    with pytest.raises(ValidationError):  # observed statistics carry their sample
        MarketStatement(kind="OBSERVED", origin="observed", section="prices", key="k", demo=False)
    with pytest.raises(ValidationError):  # free text only for AI interpretations
        MarketStatement(
            kind="FACT", origin="platform", section="supply", key="k", text="x", demo=False
        )


@pytest.mark.db
def test_small_sample_reports_gaps_not_numbers(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    for i in range(3):
        make_listing(db_session, owner, price_amount=Decimal(100_000_000 + i * 1_000_000))
    body = api.get(REPORT, params={"interpret": "false"}).json()
    kinds = {s["kind"] for s in body["statements"]}
    assert "OBSERVED" not in {s["kind"] for s in body["statements"] if s["section"] == "prices"}
    assert kinds <= {"FACT", "OBSERVED"}
    assert all(s["median_price"] is None for s in body["segments"])
    gaps = {u["metric"]: u for u in body["unavailable"]}
    assert gaps["segment_medians"]["reason"] == "sample_too_small"
    assert gaps["time_on_market"]["reason"] == "too_few_closed_listings"
    assert body["provenance"]["sample_listings"] == 3
    assert body["provenance"]["confidence"] == "low"
    assert "not transaction prices" in body["disclaimer"]


@pytest.mark.db
def test_medians_with_enough_listings_and_currencies_kept_apart(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    for i, price in enumerate((100, 120, 140, 160, 180)):
        make_listing(
            db_session,
            owner,
            price_amount=Decimal(price * 1_000_000),
            area_m2=Decimal(100 + i),
        )
    make_listing(db_session, owner, price_amount=Decimal("90000"), currency="USD")
    body = api.get(REPORT, params={"interpret": "false"}).json()
    iqd = next(s for s in body["segments"] if s["currency"] == "IQD")
    assert iqd["listings"] == 5 and iqd["median_price"] == "140000000"
    assert iqd["p25_price"] == "120000000" and iqd["p75_price"] == "160000000"
    usd = next(s for s in body["segments"] if s["currency"] == "USD")
    assert usd["median_price"] is None  # one USD listing: no statistic
    median = next(s for s in body["statements"] if s["key"] == "observed.segment_median")
    assert median["kind"] == "OBSERVED" and median["sample"] == 5
    assert median["params"]["currency"] == "IQD"


@pytest.mark.db
def test_demo_listings_are_flagged_and_can_be_excluded(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    make_listing(db_session, owner, price_amount=Decimal("100000000"))
    make_listing(db_session, owner, price_amount=Decimal("110000000"), is_demo=True)
    make_listing(db_session, owner, price_amount=Decimal("999000000"), status="DRAFT")

    body = api.get(REPORT, params={"interpret": "false"}).json()
    assert body["provenance"]["includes_demo"] is True
    assert body["provenance"]["demo_share"] == 0.5
    assert all(s["demo"] for s in body["statements"])
    active = next(s for s in body["statements"] if s["key"] == "fact.active_listings")
    assert active["params"] == {"count": 2, "demo_count": 1}  # the draft is not public

    real = api.get(REPORT, params={"interpret": "false", "include_demo": "false"}).json()
    assert real["provenance"]["includes_demo"] is False
    assert not any(s["demo"] for s in real["statements"])
    active = next(s for s in real["statements"] if s["key"] == "fact.active_listings")
    assert active["params"]["count"] == 1


@pytest.mark.db
def test_trend_needs_two_months_of_enough_listings(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    now = datetime.now(UTC)
    for month, factor in ((now - timedelta(days=62), Decimal(1)), (now, Decimal("1.1"))):
        for i in range(5):
            make_listing(
                db_session,
                owner,
                price_amount=factor * (100 + 5 * i) * 1_000_000,
                area_m2=Decimal("100"),
                published_at=month,
            )
    body = api.get(REPORT, params={"interpret": "false"}).json()
    trend = next(s for s in body["statements"] if s["key"] == "observed.price_per_m2_change")
    assert trend["kind"] == "OBSERVED" and trend["sample"] == 10
    assert trend["params"]["months"] == 2
    assert trend["params"]["change_pct"] == 10.0
    assert "price_trend" not in {u["metric"] for u in body["unavailable"]}


@pytest.mark.db
def test_city_scope_breaks_down_by_district_and_validates_args(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    make_listing(db_session, owner)
    city_id = api.get("/api/v1/market/cities").json()[0]["city_id"]
    body = api.get(REPORT, params={"city_id": city_id, "interpret": "false"}).json()
    assert body["scope"]["level"] == "city"
    assert body["provenance"]["coverage"].startswith("city:")
    bad = api.get(REPORT, params={"city_id": city_id, "governorate_id": city_id})
    assert bad.status_code == 422
    missing = api.get(REPORT, params={"district_id": "00000000-0000-0000-0000-000000000000"})
    assert missing.status_code == 404


@pytest.mark.db
def test_interpretation_is_labelled_and_cannot_invent(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    for price in (100, 120, 140, 160, 180):
        make_listing(db_session, owner, price_amount=Decimal(price * 1_000_000))

    body = api.get(REPORT, params={"language": "en"}).json()
    ai = [s for s in body["statements"] if s["origin"] == "ai"]
    assert len(ai) == 1 and ai[0]["kind"] == "AI_INTERPRETATION"
    assert ai[0]["text"].startswith("Based on the available data")

    providers.set_provider_override(InventingProvider())
    body = api.get(REPORT, params={"language": "en"}).json()
    text = next(s["text"] for s in body["statements"] if s["origin"] == "ai")
    assert "40" not in text and "guaranteed" not in text.lower()


@pytest.mark.db
def test_supply_trend_only_from_recorded_snapshots(api: TestClient, db_session: Session) -> None:
    from sqlalchemy import func, select

    from app.market.models import MarketSnapshot
    from app.market.snapshots import record_snapshot

    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    for i in range(5):
        make_listing(db_session, owner, price_amount=Decimal(100_000_000 + i * 1_000_000))
    make_listing(db_session, owner, price_amount=Decimal("90000"), currency="USD", is_demo=True)

    body = api.get(REPORT, params={"interpret": "false"}).json()
    gap = next(u for u in body["unavailable"] if u["metric"] == "supply_trend")
    assert gap["reason"] == "snapshots_too_few" and gap["detail"]["days_recorded"] == 0

    today = datetime.now(UTC).date()
    first = record_snapshot(db_session, today - timedelta(days=7))
    again = record_snapshot(db_session, today - timedelta(days=7))  # idempotent
    assert first["rows"] == again["rows"] > 0
    rows = db_session.execute(
        select(func.count()).where(MarketSnapshot.day == today - timedelta(days=7))
    ).scalar_one()
    assert rows == first["rows"]
    iraq = db_session.execute(
        select(MarketSnapshot).where(
            MarketSnapshot.scope_key == "iraq",
            MarketSnapshot.include_demo.is_(True),
            MarketSnapshot.currency == "IQD",
        )
    ).scalar_one()
    assert iraq.active_listings == 5 and iraq.median_price == Decimal("102000000.00")

    make_listing(db_session, owner, price_amount=Decimal("120000000"))
    record_snapshot(db_session, today)
    body = api.get(REPORT, params={"interpret": "false"}).json()
    change = next(s for s in body["statements"] if s["key"] == "observed.supply_change")
    assert change["kind"] == "OBSERVED" and change["sample"] == 2
    assert change["params"]["from_count"] == 6 and change["params"]["to_count"] == 7
    assert [p["active_listings"] for p in body["supply_history"]] == [6, 7]

    real = api.get(REPORT, params={"interpret": "false", "include_demo": "false"}).json()
    assert [p["active_listings"] for p in real["supply_history"]] == [5, 6]
