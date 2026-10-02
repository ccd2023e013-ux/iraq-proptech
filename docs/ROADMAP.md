# Roadmap and phase reports

| # | Phase | Status |
| --- | --- | --- |
| 1 | Foundation | Done — CI green (run 36955562983) |
| 2 | Authentication + RBAC | Not started |
| 3 | Properties | Not started |
| 4 | Search | Not started |
| 5 | GIS / Maps | Not started |
| 6 | CRM / Leads | Not started |
| 7 | AI | Not started |
| 8 | Admin / Moderation | Not started |
| 9 | Notifications / Automation | Not started |
| 10 | Analytics | Not started |
| 11 | Temporary cloud deployment | Not started |
| 12 | Production migration documentation | Not started |

A phase is only marked done after CI is green on `main`.

## Phase 1 — Foundation

**Scope:** monorepo, Codespaces dev container, Docker images and Compose
(base/dev/production), FastAPI skeleton (settings, JSON logging, error
envelope, request IDs, security headers, health/readiness), SQLAlchemy +
Alembic with PostGIS and `pg_trgm`, Celery worker, Next.js skeleton (Arabic
RTL default, English, same-origin API proxy, design tokens), tests, CI.

**Tests:**
- Backend: config parsing, health/request-ID/security-header/error-envelope
  behaviour, PostGIS distance and point-in-polygon on real Basra coordinates,
  trigram similarity on Arabic text, `system_settings` round-trip, readiness
  endpoint, migration downgrade/upgrade, model–migration drift.
- Frontend: API client (URL resolution, error envelope, network errors),
  proxy header filtering, i18n key parity and RTL default, status panel.
- Stack: full Docker Compose boot, readiness, proxy, RTL page, Celery task
  round-trip.

**Result:** all three CI jobs green on commit `1030de2`
(<https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/36955562983>).

**Errors fixed during CI:**
- Migration drift test reported the tiger-geocoder tables that the
  `postgis/postgis` image installs. Extension-owned tables are now detected from
  `pg_depend` and ignored by both `alembic/env.py` and the test.
- Prettier version mismatch between environments — pinned to an exact version.
- `docker compose up --wait` treats the one-shot `migrate` container's exit as a
  failure — replaced with `scripts/ci/wait-for-stack.sh`.

**Known limitations:**
- Supabase, Render and Cloudflare are not wired up yet (Phase 11).
- `package-lock.json` was generated and committed by CI (bootstrap step); from
  now on `npm ci` uses it.
