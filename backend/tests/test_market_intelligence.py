"""Market Intelligence: typed statements, minimum samples, honest gaps, DEMO labelling.

Each test maps to a Stage 8 audit rule: asking vs transaction prices, no
currency mixing, minimum samples, no back-filled history, demo inclusion and
exclusion, truthful confidence, district snapshot limits, possible duplicates,
per-statement provenance, guarded AI wording and distinct statement kinds.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai import providers, templates
from app.ai.providers import AIRequest, AIResponse
from app.market import intelligence, snapshots
from app.market.intelligence import MarketStatement
from app.properties.models import Property, PropertyPriceHistory, PropertyStatusHistory
from app.rbac.catalog import Role
from tests.factories import basra, make_district, make_listing, make_user

REPORT = "/api/v1/market/report"
OBS = {"source": "listings", "method": "median", "period_from": date(2026, 1, 1)}


class ScriptedProvider:
    """Returns a fixed text — used to try forbidden wording past the guards."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(data={"text": self.text}, provider=self.name, model=self.model)


@pytest.fixture(autouse=True)
def _reset_provider():
    yield
    providers.set_provider_override(None)


@pytest.fixture
def owner(db_session: Session):
    return make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])


def _price(db: Session, prop: Property, amount: str, currency: str, at: datetime) -> None:
    db.add(
        PropertyPriceHistory(
            property_id=prop.id,
            price_amount=Decimal(amount),
            currency=currency,
            price_on_request=False,
            changed_by_id=None,
            changed_at=at,
        )
    )
    db.commit()


def _report(api: TestClient, **params: str) -> dict:
    response = api.get(REPORT, params={"interpret": "false", **params})
    assert response.status_code == 200, response.text
    return response.json()


def _stmt(body: dict, key: str) -> dict | None:
    return next((s for s in body["statements"] if s["key"] == key), None)


# --- statement kinds stay distinct (no database)


def test_statement_kind_is_bound_to_its_origin() -> None:
    MarketStatement(kind="FACT", origin="platform", section="supply", key="k", demo=False, **OBS)
    with pytest.raises(ValidationError):  # AI can never be a fact
        MarketStatement(kind="FACT", origin="ai", section="supply", key="k", demo=False, **OBS)
    with pytest.raises(ValidationError):  # AI can never produce an observed statistic
        MarketStatement(
            kind="OBSERVED", origin="ai", section="prices", key="k", sample=9, demo=False, **OBS
        )
    with pytest.raises(ValidationError):  # nothing else may claim the AI source
        MarketStatement(
            kind="FACT",
            origin="platform",
            section="supply",
            key="k",
            demo=False,
            source="ai",
            method="count",
        )
    with pytest.raises(ValidationError):  # free text only for AI interpretations
        MarketStatement(
            kind="FACT", origin="platform", section="supply", key="k", text="x", demo=False, **OBS
        )
    for kind, origin in (("ESTIMATE", "observed"), ("SIMULATION", "platform")):
        with pytest.raises(ValidationError):
            MarketStatement(kind=kind, origin=origin, section="prices", key="k", demo=False, **OBS)


def test_observed_statistics_need_sample_and_period() -> None:
    ok = {**OBS, "period_to": date(2026, 2, 1)}
    MarketStatement(
        kind="OBSERVED", origin="observed", section="prices", key="k", sample=5, demo=False, **ok
    )
    with pytest.raises(ValidationError):  # below the minimum sample
        MarketStatement(
            kind="OBSERVED",
            origin="observed",
            section="prices",
            key="k",
            sample=4,
            demo=False,
            **ok,
        )
    with pytest.raises(ValidationError):  # no observation period
        MarketStatement(
            kind="OBSERVED",
            origin="observed",
            section="prices",
            key="k",
            sample=5,
            demo=False,
            source="listings",
            method="median",
        )


@pytest.mark.parametrize(
    "text",
    [
        "Prices will rise next year.",
        "A good investment with guaranteed returns.",
        "Houses sold for 120,000,000 IQD.",
        "The transaction price is 5.",
        "Based on the available data, ROI is strong.",
        "بناءً على البيانات المتاحة سترتفع الأسعار العام المقبل.",
        "فرصة استثمارية بأرباح مضمونة.",
        "سعر الصفقة 5.",
    ],
)
def test_forbidden_wording_is_detected(text: str) -> None:
    assert intelligence._forbidden_hits(text)


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_fallback_template_uses_no_forbidden_wording(lang: str) -> None:
    facts = {
        "scope_ar": "البصرة",
        "scope_en": "Basra",
        "active_listings": 12,
        "includes_demo": True,
        "segment_type_ar": "بيت",
        "segment_type_en": "House",
        "segment_purpose": "SALE",
        "segment_median": "140,000,000",
        "segment_currency": "IQD",
        "segment_sample": 5,
    }
    text = templates.market_interpretation(facts, lang)["text"]
    assert intelligence._forbidden_hits(text) == []


def test_word_boundaries_avoid_false_hits() -> None:
    assert intelligence._forbidden_hits("A heroic river view; predictable access.") == []


def test_confidence_reflects_sample_demo_and_freshness() -> None:
    now = datetime.now(UTC)
    assert intelligence._confidence(0, 0, None, now)[0] == "none"
    assert intelligence._confidence(10, 0, now, now) == (
        "low",
        ["small_sample", "asking_prices_only"],
    )
    assert intelligence._confidence(50, 0, now, now)[0] == "medium"
    assert intelligence._confidence(250, 0, now, now)[0] == "high"
    level, reasons = intelligence._confidence(250, 1, now, now)
    assert level == "low" and "demo_data" in reasons
    level, reasons = intelligence._confidence(250, 0, now - timedelta(days=120), now)
    assert level == "low" and "stale" in reasons


# --- report against the database


@pytest.mark.db
def test_small_sample_reports_gaps_not_numbers(api: TestClient, db_session: Session, owner) -> None:
    for i in range(3):
        make_listing(db_session, owner, price_amount=Decimal(100_000_000 + i * 1_000_000))
    body = _report(api)
    assert not [s for s in body["statements"] if s["kind"] == "OBSERVED"]
    assert all(s["median_price"] is None for s in body["segments"])
    gaps = {u["metric"]: u for u in body["unavailable"]}
    assert gaps["segment_medians"]["reason"] == "sample_too_small"
    assert gaps["time_on_market"]["reason"] == "too_few_closed_listings"
    assert gaps["transaction_prices"]["reason"] == "not_collected"
    assert body["provenance"]["sample_listings"] == 3
    assert body["provenance"]["confidence"] == "low"
    assert "small_sample" in body["provenance"]["confidence_reasons"]
    assert "not transaction prices" in body["disclaimer"]


@pytest.mark.db
def test_every_statement_carries_provenance(api: TestClient, db_session: Session, owner) -> None:
    for i, price in enumerate((100, 120, 140, 160, 180)):
        make_listing(
            db_session, owner, price_amount=Decimal(price * 1_000_000), area_m2=Decimal(100 + i)
        )
    body = _report(api)
    assert body["statements"]
    for s in body["statements"]:
        assert s["source"] in {
            "listings",
            "price_history",
            "status_history",
            "interest",
            "snapshots",
        }
        assert s["method"] and s["period_to"]
        if s["kind"] == "OBSERVED":
            assert s["sample"] >= 5 and s["period_from"] and s["period_to"]
    for key in ("source", "coverage", "sample_listings", "confidence", "last_update"):
        assert body["provenance"][key] is not None


@pytest.mark.db
def test_medians_with_enough_listings_and_currencies_kept_apart(
    api: TestClient, db_session: Session, owner
) -> None:
    for i, price in enumerate((100, 120, 140, 160, 180)):
        make_listing(
            db_session, owner, price_amount=Decimal(price * 1_000_000), area_m2=Decimal(100 + i)
        )
    for _ in range(4):
        make_listing(db_session, owner, price_amount=Decimal("90000"), currency="USD")
    body = _report(api)
    iqd = next(s for s in body["segments"] if s["currency"] == "IQD")
    assert iqd["listings"] == 5 and iqd["median_price"] == "140000000"
    assert iqd["p25_price"] == "120000000" and iqd["p75_price"] == "160000000"
    usd = next(s for s in body["segments"] if s["currency"] == "USD")
    assert usd["listings"] == 4 and usd["median_price"] is None  # 4 < 5: no statistic
    medians = [s for s in body["statements"] if s["key"] == "observed.segment_median"]
    assert [m["params"]["currency"] for m in medians] == ["IQD"]
    assert medians[0]["sample"] == 5


@pytest.mark.db
def test_demo_listings_are_flagged_and_can_be_excluded(
    api: TestClient, db_session: Session, owner
) -> None:
    make_listing(db_session, owner, price_amount=Decimal("100000000"))
    make_listing(db_session, owner, price_amount=Decimal("110000000"), is_demo=True)
    make_listing(db_session, owner, price_amount=Decimal("999000000"), status="DRAFT")

    body = _report(api)
    assert body["provenance"]["includes_demo"] is True
    assert body["provenance"]["demo_share"] == 0.5
    assert "demo_data" in body["provenance"]["confidence_reasons"]
    active = _stmt(body, "fact.active_listings")
    assert active["params"] == {"count": 2, "demo_count": 1}  # the draft is not public
    assert active["demo"] is True

    real = _report(api, include_demo="false")
    assert real["provenance"]["includes_demo"] is False
    assert not any(s["demo"] for s in real["statements"])
    assert _stmt(real, "fact.active_listings")["params"]["count"] == 1


@pytest.mark.db
def test_trend_uses_initial_asking_prices_by_publication_month(
    api: TestClient, db_session: Session, owner
) -> None:
    now = datetime.now(UTC)
    earlier = now - timedelta(days=62)
    for month, factor in ((earlier, Decimal(1)), (now, Decimal("1.1"))):
        for i in range(5):
            price = factor * (100 + 5 * i) * 1_000_000
            prop = make_listing(
                db_session, owner, price_amount=price, area_m2=Decimal("100"), published_at=month
            )
            _price(db_session, prop, str(price), "IQD", month)
    # A later price cut on an early listing must not rewrite what was asked then.
    cut = db_session.query(Property).filter(Property.published_at == earlier).first()
    cut.price_amount = Decimal("50000000")
    db_session.commit()
    _price(db_session, cut, "50000000", "IQD", now)

    body = _report(api)
    trend = _stmt(body, "observed.initial_price_per_m2_change")
    assert trend["kind"] == "OBSERVED" and trend["sample"] == 10
    assert trend["source"] == "price_history"
    assert trend["params"]["months"] == 2 and trend["params"]["change_pct"] == 10.0
    assert trend["period_from"] == f"{earlier:%Y-%m}-01"
    assert "price_trend" not in {u["metric"] for u in body["unavailable"]}


@pytest.mark.db
def test_no_trend_without_recorded_history(api: TestClient, db_session: Session, owner) -> None:
    """Listings without a recorded initial price are not given a made-up one."""
    earlier = datetime.now(UTC) - timedelta(days=62)
    for i in range(10):
        make_listing(
            db_session,
            owner,
            price_amount=Decimal(100_000_000 + i),
            published_at=earlier if i < 5 else datetime.now(UTC),
        )
    body = _report(api)
    assert _stmt(body, "observed.initial_price_per_m2_change") is None
    gap = next(u for u in body["unavailable"] if u["metric"] == "price_trend")
    assert gap["detail"]["months_with_enough_listings"] == 0


@pytest.mark.db
def test_price_changes_never_mix_currencies(api: TestClient, db_session: Session, owner) -> None:
    then = datetime.now(UTC) - timedelta(days=10)
    for i in range(5):
        prop = make_listing(db_session, owner, price_amount=Decimal(90_000_000 + i))
        _price(db_session, prop, str(100_000_000 + i), "IQD", then)
        _price(db_session, prop, str(90_000_000 + i), "IQD", datetime.now(UTC))
    switched = make_listing(db_session, owner, price_amount=Decimal("80000"), currency="USD")
    _price(db_session, switched, "100000000", "IQD", then)
    _price(db_session, switched, "80000", "USD", datetime.now(UTC))

    body = _report(api)
    count = _stmt(body, "fact.listings_with_price_change")
    assert count["params"] == {"count": 5, "of": 6}  # the IQD→USD switch is not a change
    change = _stmt(body, "observed.median_price_change")
    assert change["sample"] == 5 and change["params"]["change_pct"] == -10.0


@pytest.mark.db
def test_time_on_market_counts_only_marked_sold_or_rented(
    api: TestClient, db_session: Session, owner
) -> None:
    published = datetime.now(UTC) - timedelta(days=40)
    for i, status in enumerate(["SOLD"] * 3 + ["RENTED"] * 2 + ["EXPIRED"] * 4):
        prop = make_listing(db_session, owner, published_at=published, price_amount=Decimal(1 + i))
        prop.status = status
        db_session.add(
            PropertyStatusHistory(
                property_id=prop.id,
                from_status="APPROVED",
                to_status=status,
                changed_at=published + timedelta(days=10 + i),
            )
        )
        db_session.commit()
    body = _report(api)
    closed = _stmt(body, "observed.median_days_to_marked_closed")
    assert closed["sample"] == 5  # expired listings are withdrawals, not sales
    assert closed["source"] == "status_history" and closed["params"]["days"] == 12


@pytest.mark.db
def test_city_scope_compares_districts_on_one_segment(
    api: TestClient, db_session: Session, owner
) -> None:
    _, city = basra(db_session)
    district = make_district(db_session, city)
    for i in range(5):
        make_listing(
            db_session,
            owner,
            district_id=district.id,
            price_amount=Decimal(100_000_000 + i * 1_000_000),
            area_m2=Decimal("100"),
        )
    for _ in range(4):  # another type and currency must not enter the comparison
        make_listing(
            db_session,
            owner,
            district_id=district.id,
            property_type_code="APARTMENT",
            price_amount=Decimal("90000"),
            currency="USD",
        )
    body = _report(api, city_id=str(city.id))
    assert body["scope"]["level"] == "city"
    assert body["areas_basis"]["property_type_code"] == "HOUSE"
    assert body["areas_basis"]["currency"] == "IQD"
    area = next(a for a in body["areas"] if a["id"] == str(district.id))
    assert area["active_listings"] == 9 and area["sample"] == 5
    assert area["median_price_per_m2"] == "1020000" and area["currency"] == "IQD"
    assert _stmt(body, "fact.area_breakdown")["kind"] == "FACT"

    district_body = _report(api, district_id=str(district.id))
    gap = next(u for u in district_body["unavailable"] if u["metric"] == "supply_trend")
    assert gap["reason"] == "not_recorded_for_districts"
    assert district_body["supply_history"] == []


@pytest.mark.db
def test_scope_arguments_are_validated(api: TestClient, db_session: Session, owner) -> None:
    make_listing(db_session, owner)
    city_id = api.get("/api/v1/market/cities").json()[0]["city_id"]
    bad = api.get(REPORT, params={"city_id": city_id, "governorate_id": city_id})
    assert bad.status_code == 422
    missing = api.get(REPORT, params={"district_id": "00000000-0000-0000-0000-000000000000"})
    assert missing.status_code == 404


@pytest.mark.db
def test_possible_duplicates_are_only_called_possible(
    api: TestClient, db_session: Session, owner
) -> None:
    make_listing(db_session, owner, price_amount=Decimal("150000000"), area_m2=Decimal("200"))
    make_listing(db_session, owner, price_amount=Decimal("150000000"), area_m2=Decimal("201"))
    body = _report(api)
    dup = _stmt(body, "fact.possible_duplicate_pairs")
    assert dup["params"]["pairs"] == 1 and dup["method"].startswith("heuristic")
    assert not [
        s for s in body["statements"] if "duplicate" in s["key"] and "possible" not in s["key"]
    ]


@pytest.mark.db
def test_interpretation_is_labelled_and_guarded(
    api: TestClient, db_session: Session, owner
) -> None:
    for price in (100, 120, 140, 160, 180):
        make_listing(db_session, owner, price_amount=Decimal(price * 1_000_000))

    body = api.get(REPORT, params={"language": "en"}).json()
    ai = [s for s in body["statements"] if s["origin"] == "ai"]
    assert len(ai) == 1 and ai[0]["kind"] == "AI_INTERPRETATION" and ai[0]["source"] == "ai"
    assert ai[0]["text"].startswith("Based on the available data")

    for attempt in (
        "Based on the available data, prices will rise next year.",  # forecast, no numbers
        "Based on the available data, this is a good investment.",  # advice
        "Based on the available data, houses sold for these prices.",  # transaction claim
        "Based on the available data, 7 listings exist.",  # invented number
    ):
        providers.set_provider_override(ScriptedProvider(attempt))
        body = api.get(REPORT, params={"language": "en"}).json()
        text = next(s["text"] for s in body["statements"] if s["origin"] == "ai")
        assert text != attempt and intelligence._forbidden_hits(text) == []


@pytest.mark.db
def test_snapshots_are_today_only_and_feed_the_supply_trend(
    api: TestClient, db_session: Session, owner, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import select

    from app.market.models import MarketSnapshot

    for i in range(5):
        make_listing(db_session, owner, price_amount=Decimal(100_000_000 + i * 1_000_000))
    make_listing(db_session, owner, price_amount=Decimal("90000"), currency="USD", is_demo=True)

    body = _report(api)
    gap = next(u for u in body["unavailable"] if u["metric"] == "supply_trend")
    assert gap["reason"] == "snapshots_too_few" and gap["detail"]["days_recorded"] == 0

    # There is no parameter for another day: the job always records "today".
    with pytest.raises(TypeError):
        snapshots.record_snapshot(db_session, date(2020, 1, 1))  # type: ignore[call-arg]

    today = datetime.now(UTC).date()
    monkeypatch.setattr(snapshots, "_today", lambda: today - timedelta(days=7))
    first = snapshots.record_snapshot(db_session)
    again = snapshots.record_snapshot(db_session)  # idempotent
    assert first["rows"] == again["rows"] > 0
    iraq = db_session.execute(
        select(MarketSnapshot).where(
            MarketSnapshot.scope_key == "iraq",
            MarketSnapshot.include_demo.is_(True),
            MarketSnapshot.currency == "IQD",
        )
    ).scalar_one()
    assert iraq.active_listings == 5 and iraq.demo_listings == 0
    assert iraq.median_price == Decimal("102000000.00")
    usd = db_session.execute(
        select(MarketSnapshot).where(
            MarketSnapshot.scope_key == "iraq",
            MarketSnapshot.include_demo.is_(True),
            MarketSnapshot.currency == "USD",
        )
    ).scalar_one()
    assert usd.demo_listings == 1 and usd.median_price is None  # 1 < 5

    make_listing(db_session, owner, price_amount=Decimal("120000000"))
    monkeypatch.setattr(snapshots, "_today", lambda: today)
    snapshots.record_snapshot(db_session)
    body = _report(api)
    change = _stmt(body, "fact.supply_change")
    assert change["kind"] == "FACT" and change["source"] == "snapshots"
    assert change["params"]["from_count"] == 6 and change["params"]["to_count"] == 7
    assert change["demo"] is True
    assert [p["active_listings"] for p in body["supply_history"]] == [6, 7]

    real = _report(api, include_demo="false")
    assert [p["active_listings"] for p in real["supply_history"]] == [5, 6]
    assert _stmt(real, "fact.supply_change")["demo"] is False
