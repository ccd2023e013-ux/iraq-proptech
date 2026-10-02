# Phase status (checkpoints)

GitHub Actions is the verification authority: a phase is complete only when
the full CI workflow (backend on PostGIS, frontend build/tests, Docker stack
smoke tests) is green on `main`.

| Phase | Status | Verified commit | CI run |
| --- | --- | --- | --- |
| 1 Foundation | ✅ Complete | `c989590` | [36955865842](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36955865842) |
| 2 Authentication + RBAC | ✅ Complete | `ec0c09d` | [36959025895](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36959025895) |
| 3 Real estate core | ✅ Complete | `ee0b8c8` | [36960780682](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36960780682) |
| 4 Search + discovery | ⏳ In progress | | |
| 5 GIS + maps | Not started | | |
| 6 CRM + leads | Not started | | |
| 7 AI | Not started | | |
| 8 Admin + moderation | Not started | | |
| 9 Automation + notifications | Not started | | |
| 10 Analytics | Not started | | |
| 11 Temporary cloud deployment | Not started | | |
| 12 Local PC migration | Not started | | |
| Final audit + E2E | Not started | | |

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
