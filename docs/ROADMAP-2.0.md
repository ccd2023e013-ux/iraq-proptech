# Roadmap 2.0 — Iraq's intelligent property and development platform

Baseline: [PRODUCT-AUDIT-2.0.md](PRODUCT-AUDIT-2.0.md). Every stage:
separate commits, CI green, deployed to the free Render/Supabase environment,
verified by the *Live site* workflow (and screenshots for UI work), existing
API/data/security/backups preserved. A stage is "done" only when it works
live, or the reason it cannot yet be live is documented.

Status legend: ✅ done (live-verified) · 🚧 in progress · ⏳ planned ·
🔑 needs an external account/credential/data licence · ⚖️ needs legal review.

| # | Stage | Status |
| --- | --- | --- |
| 0 | Product audit | ✅ |
| 1 | Premium design system | 🚧 |
| 2 | Authentication and core UX | 🚧 |
| 3 | Basra-first Map 2.0 | ⏳ |
| 4 | Property Intelligence | ⏳ |
| 5 | Development Intelligence ("Future Iraq") | ⏳ 🔑 |
| 6 | AI Property Vision | ⏳ 🔑 |
| 7 | Property Media Studio (+ drone workflow) | ⏳ 🔑 |
| 8 | Market Intelligence | ⏳ |
| 9 | Social / Meta authorized intelligence | ⏳ 🔑 ⚖️ |
| 10 | Monetization (entitlements) | ⏳ |
| 11 | Transactions / commissions | ⏳ ⚖️ |
| 12 | Urban simulation (Basra) | ⏳ |
| 13 | Mobile apps | ⏳ |

---

## 1 — Premium design system

Calm, spatial, premium; Arabic-first typography; light, dark and system
themes; motion that explains navigation (never decoration).

- Tokens: semantic colours (surface, elevated, text tiers, accent, positive,
  caution, critical, DEMO), light + dark values, type scale (Arabic and Latin
  tuned separately), spacing, radii, elevation, blur/glass, motion durations
  and easings, `prefers-reduced-motion`.
- Theme: system default, manual override (cookie, no flash), `color-scheme`.
- Components: Button, IconButton, Input/Field, Segmented control, Chip, Badge
  (incl. DEMO / ESTIMATE / AI SIMULATION), Card surface, Sheet/Dialog,
  Skeleton, Empty state, Section header, Toast; header with translucent
  material; page transitions (View Transitions API with fallback).
- Imagery: progressive image loading (blur-up / skeleton), aspect-ratio
  locked frames, DEMO labels that never collide with UI badges.
- Homepage redesign: "Discover Iraq through property intelligence" — map/
  landscape hero with intelligent search (location, buy/rent, type, AI
  search); editorial sections: Featured Basra, Explore by area, Market
  intelligence (labelled data), Future development (honest "coming" state
  until Stage 5 data exists), AI property visualization / Media studio
  (product previews, clearly marked "coming"), Investment opportunities.
- **Acceptance**: tokens + components with unit tests; homepage, listing
  grid, property page and header redesigned; light/dark/system verified by
  screenshots on desktop and phone in Arabic and English; Lighthouse-style
  checks: no horizontal scroll, reduced motion respected, focus visible;
  live checks green.

## 2 — Authentication and core UX

- Routes: `/login`, `/register`, `/forgot-password`, `/reset-password`,
  `/verify-email` (paths match emailed links), redesigned auth shell.
- Client + server validation messages in Arabic and English; password rules
  visible; show/hide password; rate-limit and error states; `next` redirect.
- Sign-out from the header; account page polish.
- Email delivery: works with SMTP when configured (🔑 owner); without it, the
  UI says verification email is unavailable instead of failing silently.
- **Acceptance**: real-browser test on the live site (register → sign in →
  sign out → sign in; wrong password; forgot-password request; mobile
  viewport; Arabic and English), plus unit tests; live checks green.

## 3 — Basra-first Map 2.0

- Provider evaluation (MapLibre + OpenFreeMap/Protomaps/MapTiler, MapKit JS,
  Mapbox, HERE, TomTom) for Iraq: coverage, Arabic labels, satellite,
  geocoding, POIs, routing, traffic, pricing, limits, terms →
  `docs/MAP-PROVIDERS.md`; keep the provider abstraction (style + optional
  satellite/geocoder adapters).
- Price bubbles, smooth camera, selection sheet, map↔list sync, layers panel
  (areas, POIs, schools, hospitals, markets, roads), satellite toggle where a
  free/keyed source exists 🔑, radius + draw search, nearby.
- Basra depth: real OSM-derived POIs/roads (ODbL attribution) instead of DEMO
  places, where licence permits.
- **Acceptance**: browser check: bubbles render, layer toggles work, draw
  search filters results; provider doc; attribution correct.

## 4 — Property Intelligence

"Is this a good property?" — one panel combining facts, comparables, price
position, neighbourhood context, development signals and data quality, every
statement typed **FACT / SOURCE / ESTIMATE / AI INTERPRETATION / SIMULATION**.
Buyer assistant (chat over the listing's facts, injection-safe).
- **Acceptance**: typed statement schema enforced server-side; tests prove no
  AI statement can be labelled FACT; UI shows labels; works with MockAI.

## 5 — Development Intelligence ("Future Iraq")

- Source/provenance registry: source, URL, publisher, publication and
  retrieval dates, confidence, status, geometry, evidence.
- Importers for official/public sources (Ministry of Planning platform,
  National Investment Commission opportunities, provincial bodies) — only
  where terms allow; manual curation workflow in admin otherwise.
- "Future Iraq" map layer by category/status with provenance on every item.
- Never invent projects; empty state when no verified data. 🔑 (access/terms)
- **Acceptance**: provenance required by the schema (tests); admin import +
  review; layer live with real, cited items or an honest empty state.

## 6 — AI Property Vision

Upload photos/plan/parcel → conceptual renders via an image-model provider
abstraction (mock provider = labelled placeholder concepts). Every output
watermarked "AI CONCEPT — NOT AN ENGINEERING OR GOVERNMENT APPROVAL". 🔑
- **Acceptance**: job pipeline (queued → processing → done/failed), storage,
  watermark test, entitlement gate; mock provider works live.

## 7 — Property Media Studio + drone workflow

Pipeline abstraction: inputs (photos, video, drone footage, map context,
listing data) → renders (slideshow, 16:9, 9:16, captions AR/EN, map intro,
boundary animation, overlays) via pluggable render/voice providers. Initial
free implementation: server-side slideshow/caption composition within free
limits; heavy rendering via external provider later. 🔑
- **Acceptance**: job pipeline + a real slideshow export works live.

## 8 — Market Intelligence

Daily snapshots of platform listings (asking price, price/m², supply,
time-on-market, price changes, duplicates) → trends per area/type. Data
classes kept separate: verified / platform / public / AI estimate. No
back-filled history.
- **Acceptance**: snapshot job + charts live; tests for class separation.

## 9 — Social / Meta authorized intelligence ⚖️ 🔑

Only official APIs and permissions (Pages the operator manages, authorized
integrations, user-submitted posts). No scraping of private groups. Pipeline:
collect → normalize → extract (property, price, location) → dedupe → signal →
provenance; external text treated as untrusted data (prompt-injection safe).
- **Acceptance**: user-submitted ingestion works live; Meta integration only
  after app review/permissions.

## 10 — Monetization

Entitlements (Free / Professional / Agency / Enterprise) mapped to features
(AI reports, visualization, media studio, promoted listings, CRM seats,
market/development intelligence); prices configurable in admin; payment
provider abstraction stays (DEMO until an Iraqi-compatible gateway 🔑).
- **Acceptance**: entitlement checks server-side with tests; admin pricing.

## 11 — Transactions / commissions ⚖️

Inquiry → viewing → offer → negotiation → accepted → transaction →
commission → completed; parties, agent, commission rules, fees, invoices,
terms acceptance, audit trail, escrow/payment abstraction. Does **not**
legally guarantee payment; contract terms flagged for Iraqi legal review.

## 12 — Urban simulation (Basra)

Scenario engine (road, housing units, commercial centre) → accessibility,
services, development pressure, demand scenarios from transparent models;
every output labelled SIMULATION.

## 13 — Mobile apps

Evaluation React Native/Expo vs Flutter (`docs/MOBILE.md`); shared API,
auth (bearer tokens already supported), push. Build after web stages 1–4.

## Cross-cutting rules

Security for every integration (SSRF allowlists, secret isolation, upload
validation, prompt-injection isolation of external content, rate limits,
audit, permissions). Performance on the free tier (caching, lazy loading,
image sizes, tile usage, indexes). No fake data depth: unavailable data is
shown as unavailable/demo/estimated.
