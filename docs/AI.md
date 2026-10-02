# AI engine

Provider-independent, explainable and safe by construction. The platform
works fully **without any API key**: the default `mock` provider is
deterministic, offline and free. Real providers are adapters selected by
configuration.

## Providers

| `AI_PROVIDER` | Adapter | Credential | Default model (`AI_MODEL` overrides) |
| --- | --- | --- | --- |
| `mock` (default) | `MockAIProvider` — templates filled only from facts; rule-based NL parser | none | `mock-templates-v1` |
| `claude` | Anthropic Messages API over HTTPS | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` |
| `openai` | OpenAI Chat Completions (JSON mode) | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `gemini` | Google Gemini `generateContent` (JSON MIME type) | `GEMINI_API_KEY` | `gemini-1.5-flash` |

Adapters use plain `httpx` (no vendor SDKs). A provider configured without
its key falls back to `mock` instead of failing. Provider errors never echo
response bodies (they may contain prompt data). Model names change over
time — set `AI_MODEL` to the current model of your provider.

Status: the mock provider is **CI verified** end-to-end; the real adapters are
**unit tested against recorded request/response shapes** (HTTP mocked) and
**require an external credential** to be used for real.

## Safety rules (enforced in code)

1. **Facts in, facts out.** Generative tasks receive a `facts` object built
   only from what the lister declared (plus reference-data labels). The
   system prompt forbids adding prices, areas, rooms, ownership/legal status,
   amenities, features, location details or availability.
2. **Schema validation.** Every provider output must match the requested JSON
   shape; NL-search output must validate as `SearchFilters`.
3. **Fact guard** (`app/ai/guards.py`): every number in generated text must
   appear in the facts; ownership/legal claims ("طابو", "title deed"),
   "verified" and any "guaranteed return" wording are rejected unless a fact
   supports them (guarantees: never).
4. **Fallback.** A failing, invalid or fact-inventing response is replaced by
   the deterministic template and recorded with status `FALLBACK` and the
   reasons.
5. **Estimates are estimates.** Price and investment figures carry
   `kind: "estimate"`, `is_estimate: true`, a confidence, the comparable
   count and scope, methodology, limitations and a disclaimer. With fewer than
   3 comparables the value is `null` with an `unavailable_reason` — nothing is
   guessed. Currencies are never converted; demo listings never inform
   estimates for real listings.
6. **Traceability.** Every call is stored in `ai_generations` (feature, kind,
   provider, model, status, user, property/lead, redacted input summary,
   output, validation errors, confidence, latency, tokens).
7. **Quotas.** Generative calls are limited per user per day
   (`AI_DAILY_LIMIT_PER_USER`) and rate-limited per IP.

## Result envelope

```json
{
  "feature": "price.analysis",
  "kind": "estimate",
  "provider": "platform",
  "model": "statistics-v1",
  "generation_id": "…",
  "confidence": 0.23,
  "methodology": "Median and interquartile range of asking price per m² …",
  "data_sources": ["public listings on this platform"],
  "limitations": ["Based on asking prices …, not on completed transactions.", "…"],
  "disclaimer": "Estimate — not a valuation and not a verified market price.",
  "created_at": "…",
  "result": {
    "value": "300000000", "low": "285000000", "high": "315000000",
    "currency": "IQD", "price_per_m2_median": "1000000.00",
    "comparable_count": 5, "comparable_scope": "within 3 km",
    "asking_price_position": "above_range", "is_estimate": true
  }
}
```

## Features

| # | Feature | Endpoint | Kind | How |
| --- | --- | --- | --- | --- |
| 1 | Description generation | `POST /ai/listings/{id}/description` | generated | provider + guards (owner/agent only) |
| 2 | Arabic improvement | `POST /ai/text/improve-arabic` | generated | provider; numbers must be preserved exactly |
| 3 | Title generation | `POST /ai/listings/{id}/title` | generated | provider + guards |
| 4 | Summarization | `GET /ai/properties/{id}/summary` | generated | provider + guards |
| 5–6 | Search intent / NL search | `POST /ai/search/parse`, `GET /ai/search?q=` | extraction | provider (mock: rule-based Iraqi Arabic/English parser) → validated `SearchFilters`; no currency → ambiguity, never assumed |
| 7 | Recommendations | `GET /me/recommendations` | ranking | favorites + saved searches profile |
| 8 | Similar listings | `GET /ai/properties/{id}/similar` | ranking | type/purpose/currency/city; price, area, rooms, distance |
| 9 | Price analysis | `GET /ai/properties/{id}/price-analysis` | estimate | comparables median/IQR per m² |
| 10 | Investment analysis | `GET /ai/properties/{id}/investment` | estimate | gross yield from rental comparables |
| 11 | Configurable scoring | `POST /ai/properties/{id}/score` | analysis | weighted criteria; missing data excluded, not guessed |
| 12 | Neighbourhood analysis | `GET /ai/properties/{id}/neighborhood` | analysis | recorded POIs within 1.5 km + area listing statistics |
| 13 | Listing quality | `GET /ai/listings/{id}/quality` | analysis | weighted completeness checklist |
| 14 | Duplicate detection | `GET /ai/listings/{id}/duplicates` | analysis | photo pHash distance, trigram text similarity, same place & price |
| 15 | Suspicious signals | `GET /ai/listings/{id}/risk` | analysis | rule-based signals for moderators (not a verdict) |
| 16 | Lead prioritization | `GET /ai/leads/prioritized` | ranking | explainable points per factor |
| 17 | Agent assistance | `POST /ai/leads/{id}/reply-draft`, `POST /ai/leads/{id}/summary` | generated | provider + guards |
| — | Administration | `GET /admin/ai/generations`, `GET /admin/ai/usage` | — | `ai.admin` |

## Web UI

- Listing form: "Suggest a description", "Suggest titles", "Improve Arabic
  text" — drafts are shown with a note and applied only when the lister
  clicks "Use this".
- Property page: price estimate and investment analysis with confidence,
  comparables, methodology and limitations.
- `/search/smart`: natural-language search showing exactly what was
  understood, ambiguities and unparsed words, plus a link to the equivalent
  structured filters.
- CRM: AI reply draft on the lead page; AI-prioritized leads on the CRM
  dashboard.

## Adding a provider

Implement `generate(AIRequest) -> AIResponse` (see `app/ai/providers.py`),
add it to `get_provider`, add its key to settings and `.env.example`, and add
an adapter test with `httpx.MockTransport`. Guards, schema checks, fallback
and recording apply automatically.
