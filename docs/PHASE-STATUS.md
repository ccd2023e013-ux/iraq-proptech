# Phase status (checkpoints)

GitHub Actions is the verification authority: a phase is complete only when
the full CI workflow (backend on PostGIS, frontend build/tests, Docker stack
smoke tests) is green on `main`.

Phase numbers follow this repository's history. The master directive's
roadmap maps as shown in the last column.

| Phase | Status | Verified commit | CI run | Directive phase |
| --- | --- | --- | --- | --- |
| 1 Foundation | ✅ Complete | `c989590` | [36955865842](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36955865842) | 1 |
| 2 Authentication + RBAC | ✅ Complete | `ec0c09d` | [36959025895](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36959025895) | 2 |
| 3 Real estate core | ✅ Complete | `ee0b8c8` | [36960780682](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36960780682) | 3 |
| 4 Search + discovery | ✅ Complete | `ef5a719` | [36961539892](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36961539892) | 3 |
| 5 GIS + maps | ✅ Complete | `3fc684f` | [36962496975](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36962496975) | 4 |
| 5b Marketplace/GIS gap-fill (saved searches, comparison, POIs/nearby, exchange rates) | ✅ Complete | `683d92a` | [37013888512](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37013888512) | 3, 4 |
| 6 CRM + leads | ✅ Complete | `088419e` | [37019370137](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37019370137) | 5 |
| 7 AI | ✅ Complete | `088419e` | [37019370137](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37019370137) | 6 |
| 8 Admin + moderation | ✅ Complete | `088419e` | [37019370137](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37019370137) | 7 |
| 9 Automation + notifications | ✅ Complete | `43a7842` | [37021328715](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37021328715) | 8 |
| 10 Analytics | ✅ Complete | `c4a6688` | [37057349521](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37057349521) | 9 |
| 10b Monetization (demo payments) | ✅ Complete | `c4a6688` | [37057349521](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37057349521) | 10 |
| 11 Temporary cloud deployment (prepared; accounts required to go live) | ✅ Complete | `195449e` | [37065196155](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37065196155) | 11 |
| 12 Local PC migration (rehearsed in CI) | ✅ Complete | `195449e` | [37065196155](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37065196155) | 12 |
| Final security audit + 16-step E2E | ✅ Complete | `195449e` | [37065196155](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37065196155) | — |

---

## Phases 11–12 and the final audit (green at `195449e`, run [37065196155](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37065196155))

CI at this commit: backend 287 tests on PostGIS (91 % coverage), frontend 78
tests + build, Docker stack smoke (auth, listing, map) **plus the 16-step
acceptance scenario**, and the **production overlay rehearsal**.

**Phase 11 — temporary cloud deployment (prepared, not live).** Render
blueprint (`render.yaml`, free plan), Supabase guide (session pooler, private
storage bucket, transaction-pooler support), Cloudflare decision record.
Configuration preflight that stops the API on unsafe production settings;
proxy-aware client IPs (`TRUSTED_PROXY_HOPS`); worker-less operation (inline
notifications + token-protected jobs trigger called by a GitHub cron);
S3-compatible media storage tested against an in-process S3; deploy smoke
test. Going live REQUIRES the owner's Render and Supabase accounts.

**Phase 12 — production PC.** Production Compose overlay (API on 127.0.0.1,
persistent media volume), backup/restore and cloud→PC export/import scripts,
verification script, runbook with cut-over and rollback
([MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md)). CI rehearses it on every
push: production start + preflight + smoke, backup → destroy → restore, and a
data-only migration from a separate PostGIS server.

**Final audit** ([SECURITY.md](SECURITY.md)): no critical findings; fixed the
high (shared client IP behind proxies) and medium (missing web CSP,
unchecked production configuration) findings; low: proxy path hardening,
36 unindexed foreign keys indexed (migration `0013`, enforced by a new
schema test). One low race (duplicate open lead under concurrent inquiries)
is documented and accepted.

**Final E2E** (`scripts/ci/e2e-final.sh`, through the public web origin):
setup of admin, verified agency, invited agent and an approved agency
listing, then 1 register customer → 2 mock email verification → 3 login →
4 search → 5 open property → 6 favorite → 7 inquiry → 8 agent receives lead
→ 9 agent updates lead → 10 agency owner views lead → 11 admin rejects a
second listing → 12 statistical price analysis + mock-AI summary →
13 natural-language search (mock) → 14 map search → 15 notifications →
16 audit events. All 16 pass.

Errors found and fixed: `pg_restore` without a target database;
`pg_restore` 17 emitting a setting PostgreSQL 16 does not know; E2E
assumptions about response fields (agency ownership is under `lister`,
price analysis is statistics, not LLM output); a fresh-volume race where
socket `pg_isready` reported the temporary init server as ready (the
healthcheck and scripts now check over TCP). The final commit passed CI on two
consecutive attempts.

---

## Phases 9–10b — Automation, analytics, monetization

**Phase 9** (green at `43a7842`, run 37021328715): in-app notifications with
per-category preferences, outbox delivery (email/SMS/push channels, MOCK by
default), HMAC-signed webhooks with an SSRF guard (n8n-ready, never a hard
dependency), Celery beat jobs (saved-search alerts, reminders, listing expiry),
admin webhooks/jobs pages. See [AUTOMATION.md](AUTOMATION.md). Fixed: outbox
rows were not flushed before delivery (sessions do not autoflush); a typing
annotation.

**Phase 10 + 10b** (green at `c4a6688`, run 37057349521 — backend 272 tests,
91 % coverage; frontend 78 tests; Docker stack smoke incl. analytics and
billing steps): privacy-conscious analytics (unique daily visitors via
rotating salted hashes, aggregate-only search statistics without query text,
lister/agency/platform dashboards with date ranges, demo data excluded by
default) — [ANALYTICS.md](ANALYTICS.md); payment-provider abstraction with
DEMO payment mode, plans, promotions, subscriptions, refunds, all audited —
[MONETIZATION.md](MONETIZATION.md).

Errors found and fixed in 10/10b:
- `dict(Result)` treated a SQLAlchemy result as a mapping (results have
  `.keys()`), crashing dashboards once data existed — rows are now
  materialised first.
- The search-statistics test searched for a word its listing did not contain.
- The N+1 guard counted the constant search-statistics upsert; it now counts
  the reads that build a result page.

---

## Phases 6–8 — CRM, AI, Admin + moderation (verified together at `088419e`)

Phases 6, 7 and 8 were pushed in sequence; intermediate runs exposed type,
formatting and test-measurement issues that were fixed in follow-up commits.
The first fully green run covering all three is 37019370137 (backend 240
tests, 91 % coverage; frontend 74 tests; Docker stack + auth/listing/map
smoke incl. CRM steps 12–14 and moderation/report steps 15–16).

**Implemented**: see [CRM.md](CRM.md), [AI.md](AI.md) and the admin section
of [API.md](API.md). Highlights — inquiries → leads with agency scoping,
pipeline, notes, tasks, appointments, conversation threads; provider-neutral
AI (mock default) with 17 features, explainable estimates and fact guards;
reports, moderation reason codes, queues, admin console, error log, typed
settings whitelist.

**Errors found and fixed**: mypy Optional narrowing and dict-key typing;
query-count test counted SAVEPOINT bookkeeping; equal transaction timestamps
broke message ordering; error-log request id lost after context reset;
Google font fetch flaked in CI (self-hosted fonts).

---

## Phase 5 — GIS + maps

**Implemented**
- `GET /map/properties`: GeoJSON for any search filters + viewport; points
  with popup data or, above 1,500 matches, server-side clusters
  (`ST_SnapToGrid`) sized by zoom. Public display points only.
- Boundaries as GeoJSON, children boundaries (simplified), point → place
  resolution (boundary, else nearest city centroid ≤ 40 km flagged
  approximate, else none; outside Iraq → 422).
- Admin API (`locations.manage`) to create cities/districts/neighborhoods and
  set/clear validated, repaired polygons; audited.
- DEMO seed CLI: Basra districts with clearly labelled placeholder squares
  and demo listings (idempotent, reset command, refused in production).
- Map provider abstraction (OpenFreeMap default, OSM raster, custom style
  URL for self-hosting), read at runtime.
- `/map` page: URL-synced list + map, clustering, polygon drawing,
  hover/click sync, boundary source disclosure; location picker with
  suggested (never auto-applied) area in the listing form.
- CI: lockfile reconciliation when a dependency is added; GIS smoke test.

**Tests**: 25 GIS tests (privacy, filters, clustering, Iraqi coordinates —
Basra, Baghdad, Erbil, Mosul; Kuwait-inside-bbox and Tehran negatives,
boundary validation and repair, permissions, audit, demo seed); frontend
tests for provider config and geo helpers; Docker GIS smoke test.

**Errors found and fixed**: GeoJSON types not resolvable as a global
namespace (explicit imports); a WKT element passed to a generic SQL function
could not be bound (built in SQL instead); a test assumption that the nearest
city to the Corniche is Basra (Shatt Al-Arab's centroid is nearer).

**Known limitations**: no official boundary dataset bundled; demo squares
are placeholders. Basemap tiles come from a free public service in
development; self-host for production.

---

## Phase 4 — Search + discovery

**Implemented**
- `normalize_ar()` SQL function (hamza/alef forms, ى→ي, ة→ه, diacritics,
  tatweel, Arabic-Indic digits) and generated `search_text` /
  `search_vector` columns with GIN (FTS + trigram) indexes; composite
  status/price/area indexes.
- `GET`/`POST /search/properties`: keyword (FTS, typo-tolerant trigram word
  similarity, location names), location hierarchy, types, purpose, rent
  period, price range **per currency** (never converted), area, rooms,
  amenities (all-of), furnishing, condition, verified, demo exclusion,
  agency/agent, recency, bbox / radius / polygon on the public display point;
  sorts newest, price, area, relevance, distance; pagination with a deep-page
  guard; constant query count (no N+1). Unknown filters are rejected.
- Favorites API (idempotent, public listings only).
- Web: landing page (hero search, categories, governorates, latest, trust,
  call to action), results page with filters/sort/pagination, property detail
  (gallery, declared facts only, privacy-aware location, price history,
  transparent verification, consented contact, share/save), favorites page,
  status page.

**Tests**: 18 new backend search tests (Arabic spelling variants, typos,
location names, every filter, currency isolation, sorting/pagination,
spatial filters, query-count guard, favorites); frontend tests for URL⇄API
mapping and hero search; Docker smoke test searches with a spelling variant,
checks the currency filter, favorites a listing and renders the search,
detail and favorites pages server-side.

**Errors found and fixed**
- Price sorting without a currency filter compared IQD and USD amounts
  directly — now grouped by currency.
- OpenAPI/docs were exposed in production — now disabled there (tested).
- A strict-index TypeScript error in a test.

**Known limitations**: relevance ranking is FTS + trigram (no learning to
rank); saved searches arrive with Phase 9.

---

## Phase 3 — Real estate core

**Implemented**
- Iraqi location hierarchy: 19 governorates, capitals and major cities
  (approximate centroids, `geometry_source` recorded), districts and
  neighborhoods with optional PostGIS boundaries.
- Property types and amenities catalogs (Arabic/English), agencies with
  members (owner/agent) and invitations, verification flag.
- Properties: purposes (sale, rent, lease, rahn, musataha, exchange), IQD/USD
  in original currency (no conversion), rent period, area/land area, rooms,
  condition, furnishing, declared ownership document, contact consent,
  location privacy (EXACT / APPROXIMATE / HIDDEN — public coordinates are
  coarsened server-side), reference codes `{GOV}-{seq}`, demo flag, status
  machine (DRAFT → PENDING_REVIEW → APPROVED/REJECTED, SUSPENDED, ARCHIVED,
  SOLD/RENTED), status and price history, verifications.
- Media: images (magic-byte sniffing, WebP re-encode, EXIF stripped,
  thumbnails, perceptual hash for duplicate detection), documents (private),
  videos; ordering/cover; storage abstraction (local disk or any
  S3-compatible bucket).
- Policies module for object-level authorization; presenter with batch
  loading (no N+1).
- Web: listing form (create/edit), media and document manager, listing
  actions per status, "my listings", agency panels.

**Tests**: 145 backend tests (90% coverage) incl. IDOR attempts, status
transitions, privacy coarsening, upload attacks (polyglots, wrong types,
oversize), reference codes, a fresh-process mapper test and a CLI subprocess
test; frontend tests for listing form/actions; Docker smoke test creates a
listing, uploads an image through the proxy, moderates and views it publicly.

**Errors found and fixed**
- The CLI (`create-superadmin`) created a session without importing the
  model registry (same class of bug as Phase 2) — `get_sessionmaker()` now
  imports the registry itself; covered by a subprocess test.
- An unused `type: ignore` flagged by mypy.

**Known limitations**: governorate/city boundaries are not shipped (no
openly-licensed, verified dataset bundled); only centroids, marked
approximate. Video files are stored as uploaded (no transcoding).

---

## Phase 2 — Authentication + RBAC

**Implemented**
- Accounts: Argon2id passwords with a policy, Iraqi phone normalization
  (E.164), statuses, email/phone verification timestamps, soft delete.
- Sessions: JWT access tokens (15 min) bound to server-side `auth_sessions`
  rows (instant revocation), opaque rotating refresh tokens (SHA-256 stored)
  with reuse detection, logout / logout-all / per-device revocation.
- Browser transport: httpOnly cookies + double-submit CSRF; bearer transport
  for mobile/integrations (`X-Auth-Transport: bearer`).
- Email verification and password reset with single-use hashed tokens;
  MOCK email provider (dev outbox endpoint, never mounted in production) and
  SMTP provider.
- RBAC: 7 roles, 30 permissions, code-defined catalog mirrored in `roles`;
  role hierarchy for admin actions; SUPER_ADMIN only via CLI.
- Audit log written in the same transaction as each change.
- Rate limiting (Redis, in-memory fallback, hashed keys).
- Web: login, register, forgot/reset password, verify email, account
  (profile, password, devices), dashboard shell, header user menu,
  middleware route guard with server-side session renewal, open-redirect-safe
  `next` handling, single-flight client-side renewal.

**Tests**: 52 backend tests added (auth flows, forged/expired tokens, refresh
reuse, CSRF, password reset, sessions, RBAC escalation attempts, hierarchy,
audit, rate limits, security primitives); frontend tests for the API client
(CSRF, renewal, single-flight), proxy cookies, routing guard, open
redirects, login form; Docker smoke test runs the full auth flow through the
frontend proxy.

**Errors found and fixed**
- `email-validator` rejects special-use domains (`.test`) — tests use
  `example.com`.
- A mocked `Response` reused across calls in a frontend test.
- **Real bug caught by the Docker smoke test:** a fresh API process did not
  register every ORM model, so the first write failed
  (`NoReferencedTableError`). The API and worker now import the model
  registry at startup.

**Known limitations**: simultaneous refresh from two browser tabs can trigger
reuse detection (documented in AUTHENTICATION.md); SMS/phone verification
delivery arrives with Phase 9 providers.

---

## Phase 1 — Foundation

Monorepo, Codespaces dev container, Docker images and Compose
(base/dev/production), FastAPI skeleton, SQLAlchemy + Alembic with PostGIS
and `pg_trgm`, Celery worker, Next.js Arabic-RTL skeleton with same-origin
API proxy, CI. See [ROADMAP.md](ROADMAP.md) for details.
