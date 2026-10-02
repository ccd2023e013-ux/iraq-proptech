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
| 5b Marketplace/GIS gap-fill (saved searches, comparison, POIs/nearby, exchange rates) | ⏳ Next | | | 3, 4 |
| 6 CRM + leads | ⏳ In progress (WIP not pushed) | | | 5 |
| 7 AI | Not started | | | 6 |
| 8 Admin + moderation | Not started | | | 7 |
| 9 Automation + notifications | Not started | | | 8 |
| 10 Analytics | Not started | | | 9 |
| 10b Monetization (demo payments) | Not started | | | 10 |
| 11 Temporary cloud deployment | Not started | | | 11 |
| 12 Local PC migration | Not started | | | 12 |
| Final audit + E2E | Not started | | | — |

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
