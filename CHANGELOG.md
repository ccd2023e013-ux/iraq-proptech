# Changelog

All notable changes, newest first. Each entry lists the CI-verified commit.

## 2.0 Stage 5: Development Intelligence — Future Iraq (`6236919`)
Provenance model (sources, projects, evidence); five official-source Basra
records; `/future` page with sources and dates; Future Iraq map layer;
property intelligence cites nearby projects.

## 2.0 Stage 4: Property Intelligence (`e8d6fda`)
"Is this a good property?" report with statements typed FACT / SOURCE /
ESTIMATE / AI_INTERPRETATION (kind bound to origin server-side), sources and
confidence; buyer assistant answering only from the same evidence
(injection-safe); property page panel; live browser check.

## 2.0 Stage 3: Basra-first Map 2.0 (`d2849a0`)
Map provider evaluation for Iraq (docs/MAP-PROVIDERS.md); price tags,
grouped circles, layers panel (areas, places, optional satellite), selection
card, theme-following basemap, Near me; 1,372 real Basra places from
OpenStreetMap (`import-osm-pois`, ODbL attribution); homepage "Properties
near you". Fixes on the way: tags hidden by an empty stretchY, clustering at
fractional city zoom, map clicks zooming while drawing.

## 2.0 Stages 1–2: design system and working authentication (`bdc731f`)
Light/dark/system themes on semantic tokens, new header/footer/components,
new homepage (intelligent search, river map, Basra first, labelled market
reading), calmer property page, skeleton screens, `/market/*` API. Sign-in,
registration and recovery pages (previously 404) with validation, show/hide
password and honest "email unavailable" messaging (`/auth/capabilities`).
Live site workflow now runs the full auth journey and dark-mode checks in a
real browser. Fixes found on the way: phone header wrapping, auth layout
overflowing phones (and a width check that mobile zoom-out had hidden),
smoke checks failing on streamed pages, deploy wait rejecting CI's lockfile
commit.

## Online launch (`4ae902d`)
Live at https://iraq-proptech-web.onrender.com (Render free + Supabase free).
National Iraqi DEMO dataset (126 listings, 7 cities, generated DEMO images),
demo accounts, labelled MockAI features (summary, comparison), Live site
verification workflow (database audit, acceptance, real browser, security,
backup → restore). Launch fixes: web health check on /healthz, blank map
(container height), CSP allows WebAssembly for Arabic map labels,
TRUSTED_PROXY_HOPS=6 measured on Render, tolerant S3 endpoint parsing,
preflight warnings for malformed S3 endpoint / rejected demo password.

## Final audit + acceptance scenario (`195449e`)
Security audit (see docs/SECURITY.md): web CSP, proxy path hardening, all
foreign keys indexed (migration 0013) with a schema test; 16-step E2E
acceptance scenario in CI.

## Phase 12 — Production PC migration (`195449e`)
Production overlay, backup/restore, cloud→PC data-only export/import,
verification and deploy smoke scripts; full runbook rehearsed in CI.

## Phase 11 — Temporary cloud deployment (`195449e`)
Render blueprint, Supabase and Cloudflare guides, preflight checks,
`TRUSTED_PROXY_HOPS`, jobs trigger + scheduled workflow, S3 storage,
transaction-pooler support.

## Phase 10b — Monetization (`c4a6688`)
Payment-provider abstraction, DEMO payment mode, plans, promotions,
subscriptions, refunds.

## Phase 10 — Analytics (`c4a6688`)
Privacy-conscious listing views, search statistics, scoped dashboards.

## Phase 9 — Notifications + automation (`43a7842`)
In-app/email/SMS/push notifications with preferences, outbox, signed
webhooks with SSRF guard, scheduled jobs.

## Phase 8 — Admin + moderation (`088419e`)
Listing/user reports, moderation reason codes, review queues, admin console
(overview, moderation, reports, verification, users, audit, AI usage,
settings, system/errors), typed runtime settings, site announcement.

## Phase 7 — AI (`088419e`)
Provider abstraction (mock default; Claude/OpenAI/Gemini with keys), fact
guards, explainable price estimates, NL search, authoring assistant, reply
drafts, lead prioritisation, usage limits and logging.

## Phase 6 — CRM + leads (`088419e`)
Inquiries, leads with agency scoping, pipeline, notes, tasks, appointments,
conversation threads, CRM dashboard and messages UI.

## Phase 5b — Discovery gap-fill (`683d92a`)
Saved searches, property comparison, POIs + nearby, exchange-rate
abstraction with indicative conversion.

## Phase 5 — GIS + maps (`3fc684f`)
Map GeoJSON with server clustering, boundaries API, point resolution, admin
boundary management, labelled DEMO seed, MapLibre map search page, location
picker, map provider abstraction.

## Phase 4 — Search + discovery (`ef5a719`)
Arabic-normalized full-text + trigram search, structured and spatial filters,
sorting, favorites, landing/results/detail/favorites pages.

## Phase 3 — Real estate core (`ee0b8c8`)
Locations, property types, amenities, agencies, listings lifecycle, media and
documents with safe image processing, verification, listing management UI.

## Phase 2 — Authentication + RBAC (`ec0c09d`)
Argon2id, JWT + rotating refresh tokens, cookies + CSRF, email verification,
password reset, sessions, roles and permissions, audit log, rate limiting.

## Phase 1 — Foundation (`c989590`)
Monorepo, Docker Compose, FastAPI, PostGIS, Redis, Celery, Next.js RTL, CI.
