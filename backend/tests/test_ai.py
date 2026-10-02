"""AI engine: providers, guards, generative features, estimates, analysis, NL search."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import guards, providers
from app.ai import service as ai_service
from app.ai.models import AIGeneration
from app.ai.nlsearch import parse
from app.ai.providers import (
    AIProviderError,
    AIRequest,
    AIResponse,
    ClaudeProvider,
    GeminiProvider,
    MockAIProvider,
    OpenAIProvider,
    get_provider,
)
from app.core.config import Settings, get_settings
from app.rbac.catalog import Role
from tests.factories import BASRA_CORNICHE, auth_headers, make_listing, make_user

REQUEST = AIRequest(
    task="listing.description",
    system="s",
    facts={"type_ar": "بيت", "area_m2": "200"},
    output_schema={"type": "object"},
)


# --- providers (no database)


def test_mock_is_the_default_and_misconfiguration_falls_back() -> None:
    assert isinstance(get_provider(Settings()), MockAIProvider)
    assert isinstance(get_provider(Settings(ai_provider="claude")), MockAIProvider)  # no key
    assert isinstance(
        get_provider(Settings(ai_provider="claude", anthropic_api_key="k")), ClaudeProvider
    )
    assert isinstance(
        get_provider(Settings(ai_provider="openai", openai_api_key="k")), OpenAIProvider
    )
    assert isinstance(
        get_provider(Settings(ai_provider="gemini", gemini_api_key="k")), GeminiProvider
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_claude_adapter_request_and_parsing() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-test",
                "content": [{"type": "text", "text": '```json\n{"description": "بيت"}\n```'}],
                "usage": {"input_tokens": 12, "output_tokens": 5},
            },
        )

    provider = ClaudeProvider("secret-key", "claude-test", Settings(), _client(handler))
    response = provider.generate(REQUEST)
    assert response.data == {"description": "بيت"}
    assert (response.input_tokens, response.output_tokens) == (12, 5)
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "secret-key"
    assert seen["body"]["system"] == "s"
    assert "FACTS" in seen["body"]["messages"][0]["content"]


def test_openai_and_gemini_adapters() -> None:
    def openai(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer k"
        assert json.loads(request.content)["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "model": "gpt-test",
                "choices": [{"message": {"content": '{"description": "x"}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    def gemini(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "k"
        assert ":generateContent" in str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"description": "y"}'}]}}],
                "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 1},
            },
        )

    assert OpenAIProvider("k", None, Settings(), _client(openai)).generate(REQUEST).data == {
        "description": "x"
    }
    assert GeminiProvider("k", None, Settings(), _client(gemini)).generate(REQUEST).data == {
        "description": "y"
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"error": "secret prompt echoed"}),
        httpx.Response(200, json={"content": [{"type": "text", "text": "not json"}]}),
        httpx.Response(200, json={"content": [{"type": "text", "text": "[1, 2]"}]}),
    ],
)
def test_provider_errors_are_contained(response: httpx.Response) -> None:
    provider = ClaudeProvider("k", None, Settings(), _client(lambda r: response))
    with pytest.raises(AIProviderError) as info:
        provider.generate(REQUEST)
    assert "secret prompt" not in str(info.value)


def test_fact_guard() -> None:
    facts = {"area_m2": "200", "price_text": "150,000,000 IQD", "bedrooms": 3}
    assert guards.check_text("بيت 200 م² بثلاث غرف، السعر 150,000,000 IQD", facts) == []
    assert guards.check_text("بيت بمساحة 250 م²", facts) == ["number_not_in_facts:250"]
    assert guards.check_text("العقار طابو صرف", facts) == ["unsupported_claim:ownership"]
    assert guards.check_text("العقار طابو صرف", {"ownership_declared": "طابو صرف"}) == []
    assert guards.check_text("أرباح مضمونة", {}) == ["unsupported_claim:guarantee"]
    assert guards.check_text("إعلان موثق", {"verified": True}) == []


def test_nl_parser_never_guesses_currency() -> None:
    vocab = {"cities": [{"id": "c1", "names": ["البصرة", "Basra"]}]}
    result = parse("بيت للبيع في البصرة 3 غرف بأقل من 200 مليون دينار", vocab)
    assert result["filters"] == {
        "purpose": "SALE",
        "property_types": ["HOUSE"],
        "bedrooms_min": 3,
        "currency": "IQD",
        "max_price": "200000000",
        "city_id": "c1",
    }
    vague = parse("بيت بـ 150 ألف", vocab)
    assert "max_price" not in vague["filters"] and vague["ambiguities"] == [
        "currency_not_specified"
    ]
    english = parse("2 bedroom apartment for rent monthly under $800 with elevator", vocab)
    assert english["filters"]["currency"] == "USD" and english["filters"]["max_price"] == "800"
    assert english["filters"]["rent_period"] == "MONTHLY"
    assert english["filters"]["amenities"] == ["ELEVATOR"]


# --- database-backed features


class InventingProvider:
    """A provider that makes up a price and an ownership claim."""

    name = "fake"
    model = "fake-1"

    def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            data={"description": "بيت طابو صرف بسعر 999 مليون", "highlights": []},
            provider=self.name,
            model=self.model,
        )


class BrokenProvider:
    name = "broken"
    model = "broken-1"

    def generate(self, request: AIRequest) -> AIResponse:
        raise AIProviderError("timeout")


@pytest.fixture
def owner(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


@pytest.fixture(autouse=True)
def _reset_provider():
    yield
    providers.set_provider_override(None)


@pytest.mark.db
def test_description_uses_only_declared_facts(api: TestClient, db_session: Session, owner) -> None:
    listing = make_listing(
        db_session, owner, area_m2=Decimal("220"), bedrooms=4, amenities=["PARKING"]
    )
    headers = auth_headers(api, owner)
    response = api.post(
        f"/api/v1/ai/listings/{listing.id}/description", headers=headers, json={"language": "ar"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "generated" and body["provider"] == "mock"
    text = body["result"]["description"]
    assert "220" in text and "4" in text
    assert guards.check_text(text, ai_service.property_facts(db_session, listing)) == []
    row = db_session.get(AIGeneration, body["generation_id"])
    assert row.feature == "listing.description" and row.status == "SUCCEEDED"
    assert row.user_id == owner.id

    en = api.post(
        f"/api/v1/ai/listings/{listing.id}/title", headers=headers, json={"language": "en"}
    ).json()
    assert 1 <= len(en["result"]["titles"]) <= 3


@pytest.mark.db
def test_invented_facts_are_rejected_and_replaced(
    api: TestClient, db_session: Session, owner
) -> None:
    listing = make_listing(db_session, owner, area_m2=Decimal("150"))
    headers = auth_headers(api, owner)
    for provider, expected_status in (
        (InventingProvider(), "FALLBACK"),
        (BrokenProvider(), "FALLBACK"),
    ):
        providers.set_provider_override(provider)
        body = api.post(
            f"/api/v1/ai/listings/{listing.id}/description", headers=headers, json={}
        ).json()
        assert "999" not in body["result"]["description"]
        assert "طابو" not in body["result"]["description"]
        assert body["provider"] == "mock"
        row = db_session.get(AIGeneration, body["generation_id"])
        assert row.status == expected_status
        assert any(e.startswith(provider.name) for e in row.validation_errors)


@pytest.mark.db
def test_authoring_permissions(api: TestClient, db_session: Session, owner) -> None:
    listing = make_listing(db_session, owner)
    draft = make_listing(db_session, owner, status="DRAFT")
    other = auth_headers(api, make_user(db_session, roles=[Role.PROPERTY_OWNER]))
    customer = auth_headers(api, make_user(db_session))
    url = f"/api/v1/ai/listings/{listing.id}/description"
    assert api.post(url, headers=other, json={}).status_code == 403
    assert (
        api.post(f"/api/v1/ai/listings/{draft.id}/description", headers=other, json={}).status_code
        == 404
    )
    assert api.post(url, headers=customer, json={}).status_code == 403
    assert api.post(url, json={}).status_code == 401


@pytest.mark.db
def test_improve_arabic_preserves_numbers(api: TestClient, db_session: Session, owner) -> None:
    headers = auth_headers(api, owner)
    text = "بيت للبيع  ,مساحته 200 متر  ??السعر 150 مليون"
    body = api.post("/api/v1/ai/text/improve-arabic", headers=headers, json={"text": text}).json()
    improved = body["result"]["text"]
    assert "،" in improved and "؟" in improved and "  " not in improved
    assert guards._numbers(improved) == guards._numbers(text)


@pytest.mark.db
def test_daily_quota(
    api: TestClient, db_session: Session, owner, monkeypatch: pytest.MonkeyPatch
) -> None:
    limited = get_settings().model_copy(update={"ai_daily_limit_per_user": 1})
    monkeypatch.setattr(ai_service, "get_settings", lambda: limited)
    headers = auth_headers(api, owner)
    payload = {"text": "نص تجريبي قصير"}
    assert (
        api.post("/api/v1/ai/text/improve-arabic", headers=headers, json=payload).status_code == 200
    )
    blocked = api.post("/api/v1/ai/text/improve-arabic", headers=headers, json=payload)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "AI_QUOTA_EXCEEDED"


def _comps(db: Session, lister, n: int, **fields) -> list:
    fixed_price = fields.pop("price_amount", None)
    out = []
    for i in range(n):
        price = fixed_price or Decimal(str(180_000_000 + i * 10_000_000))  # 0.9–1.1 M / m²
        out.append(
            make_listing(
                db,
                lister,
                point=(BASRA_CORNICHE[0] + 0.001 * i, BASRA_CORNICHE[1]),
                privacy="EXACT",
                area_m2=Decimal("200"),
                price_amount=price,
                **fields,
            )
        )
    return out


@pytest.mark.db
def test_price_estimate_is_explainable(api: TestClient, db_session: Session, owner) -> None:
    subject = make_listing(
        db_session,
        owner,
        point=BASRA_CORNICHE,
        privacy="EXACT",
        area_m2=Decimal("300"),
        price_amount=Decimal("600000000"),
    )
    url = f"/api/v1/ai/properties/{subject.id}/price-analysis"
    early = api.get(url).json()
    assert early["result"]["value"] is None
    assert early["result"]["unavailable_reason"] == "insufficient_comparables"

    _comps(db_session, owner, 5)
    _comps(db_session, owner, 3, currency="USD", price_amount=Decimal("100"))  # other currency
    _comps(db_session, owner, 3, is_demo=True, price_amount=Decimal("1"))  # demo never counts
    body = api.get(url).json()
    result = body["result"]
    assert body["kind"] == "estimate" and result["is_estimate"] is True
    assert result["comparable_count"] == 5 and result["currency"] == "IQD"
    assert result["price_per_m2_median"] == "1000000.00"
    assert result["value"] == "300000000"
    assert result["asking_price_position"] == "above_range"
    assert 0 < body["confidence"] <= 0.9
    assert any("asking prices" in item for item in body["limitations"])
    assert body["disclaimer"]


@pytest.mark.db
def test_investment_yield_needs_rental_comparables(
    api: TestClient, db_session: Session, owner
) -> None:
    subject = make_listing(
        db_session,
        owner,
        point=BASRA_CORNICHE,
        privacy="EXACT",
        area_m2=Decimal("200"),
        price_amount=Decimal("240000000"),
    )
    url = f"/api/v1/ai/properties/{subject.id}/investment"
    assert api.get(url).json()["result"]["unavailable_reason"] == "insufficient_rental_comparables"
    _comps(
        db_session, owner, 4, purpose="RENT", rent_period="MONTHLY", price_amount=Decimal("1000000")
    )
    result = api.get(url).json()["result"]
    assert result["estimated_monthly_rent"] == "1000000"
    assert result["gross_yield_percent"] == "5.00"  # 12M / 240M
    rental = make_listing(db_session, owner, purpose="RENT", rent_period="MONTHLY")
    assert (
        api.get(f"/api/v1/ai/properties/{rental.id}/investment").json()["result"][
            "unavailable_reason"
        ]
        == "only_for_sale_listings"
    )


@pytest.mark.db
def test_score_excludes_criteria_without_data(api: TestClient, db_session: Session, owner) -> None:
    subject = make_listing(db_session, owner, amenities=["PARKING"])
    body = api.post(
        f"/api/v1/ai/properties/{subject.id}/score",
        json={"weights": {"value": 2}, "wanted_amenities": ["PARKING", "GARDEN"]},
    ).json()
    result = body["result"]
    assert result["criteria"]["amenities"] == 50.0
    assert result["criteria"]["value"] is None and "value" in result["excluded"]
    assert result["criteria"]["verification"] == 0.0
    assert result["overall"] is not None


@pytest.mark.db
def test_quality_duplicates_and_risk(api: TestClient, db_session: Session, owner) -> None:
    text = "بيت للبيع في العشار مساحة كبيرة وموقع ممتاز قريب من الخدمات " * 2
    original = make_listing(
        db_session, owner, point=BASRA_CORNICHE, privacy="EXACT", description_ar=text
    )
    scammer = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    copy = make_listing(
        db_session,
        scammer,
        point=BASRA_CORNICHE,
        privacy="EXACT",
        description_ar=text + " اتصل 07701234567",
    )
    owner_h = auth_headers(api, owner)
    quality = api.get(f"/api/v1/ai/listings/{original.id}/quality", headers=owner_h).json()
    assert "photos" in quality["result"]["suggestions"]

    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    dupes = api.get(f"/api/v1/ai/listings/{copy.id}/duplicates", headers=moderator).json()
    reasons = {r["reason"] for c in dupes["result"]["candidates"] for r in c["reasons"]}
    assert {"similar_text", "same_place_and_price"} <= reasons
    risk = api.get(f"/api/v1/ai/listings/{copy.id}/risk", headers=moderator).json()
    signals = {s["signal"] for s in risk["result"]["signals"]}
    assert "contact_details_in_description" in signals and "no_photos" in signals
    assert api.get(f"/api/v1/ai/listings/{copy.id}/risk", headers=owner_h).status_code == 403
    stranger = auth_headers(api, make_user(db_session))
    assert (
        api.get(f"/api/v1/ai/listings/{original.id}/quality", headers=stranger).status_code == 404
    )


@pytest.mark.db
def test_similar_and_recommendations(api: TestClient, db_session: Session, owner) -> None:
    subject = make_listing(db_session, owner, point=BASRA_CORNICHE, privacy="EXACT")
    close = make_listing(
        db_session, owner, point=(BASRA_CORNICHE[0] + 0.002, BASRA_CORNICHE[1]), privacy="EXACT"
    )
    make_listing(db_session, owner, property_type_code="SHOP")  # different type
    similar = api.get(f"/api/v1/ai/properties/{subject.id}/similar").json()
    assert similar["items"][0]["id"] == str(close.id)
    assert "nearby" in similar["envelope"]["result"]["items"][0]["reasons"]

    customer = make_user(db_session)
    headers = auth_headers(api, customer)
    api.put(f"/api/v1/properties/{subject.id}/favorite", headers=headers)
    recs = api.get("/api/v1/me/recommendations", headers=headers).json()
    ids = [c["id"] for c in recs["items"]]
    assert str(subject.id) not in ids and str(close.id) in ids
    assert "property_types" in recs["envelope"]["result"]["basis"]


@pytest.mark.db
def test_natural_language_search_end_to_end(api: TestClient, db_session: Session, owner) -> None:
    house = make_listing(db_session, owner, bedrooms=3, price_amount=Decimal("150000000"))
    make_listing(db_session, owner, bedrooms=1, price_amount=Decimal("150000000"))
    make_listing(db_session, owner, bedrooms=4, price_amount=Decimal("900000000"))
    body = api.get(
        "/api/v1/ai/search", params={"q": "بيت للبيع في البصرة 3 غرف بأقل من 200 مليون دينار"}
    ).json()
    filters = body["interpretation"]["result"]["filters"]
    assert filters["currency"] == "IQD" and filters["bedrooms_min"] == 3
    assert "city_id" in filters
    assert [i["id"] for i in body["items"]] == [str(house.id)]
    parsed = api.post("/api/v1/ai/search/parse", json={"query": "شقة بـ 100 ألف"}).json()
    assert parsed["result"]["ambiguities"] == ["currency_not_specified"]


@pytest.mark.db
def test_lead_assistance_and_admin_usage(api: TestClient, db_session: Session, owner) -> None:
    listing = make_listing(db_session, owner)
    customer = make_user(db_session, name="سارة")
    api.post(
        f"/api/v1/properties/{listing.id}/inquiries",
        headers=auth_headers(api, customer),
        json={"name": "سارة", "phone": "07701234567", "message": "هل العقار متاح؟"},
    )
    owner_h = auth_headers(api, owner)
    ranked = api.get("/api/v1/ai/leads/prioritized", headers=owner_h).json()
    lead_id = ranked["result"]["items"][0]["lead_id"]
    assert ranked["result"]["items"][0]["score"] > 0
    draft = api.post(f"/api/v1/ai/leads/{lead_id}/reply-draft", headers=owner_h, json={}).json()
    assert "سارة" in draft["result"]["reply"]
    other = auth_headers(api, make_user(db_session, roles=[Role.AGENT]))
    assert (
        api.post(f"/api/v1/ai/leads/{lead_id}/reply-draft", headers=other, json={}).status_code
        == 404
    )

    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    usage = api.get("/api/v1/admin/ai/usage", headers=admin).json()
    assert {"lead.reply", "lead.priority"} <= {u["feature"] for u in usage}
    generations = api.get(
        "/api/v1/admin/ai/generations", headers=admin, params={"feature": "lead.reply"}
    ).json()
    assert generations["total"] == 1
    assert api.get("/api/v1/admin/ai/usage", headers=owner_h).status_code == 403
    count = db_session.execute(select(AIGeneration)).scalars().all()
    assert len(count) >= 3
