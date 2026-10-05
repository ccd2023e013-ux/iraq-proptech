# Deployment

One codebase, two Docker images (`backend/Dockerfile`, `frontend/Dockerfile`),
three ways to run them. No environment needs a code change.

| Target | Status | Guide |
| --- | --- | --- |
| Local / Codespaces development | CI VERIFIED (`docker compose up`) | [DEVELOPMENT.md](DEVELOPMENT.md), [ONLINE-DEVELOPMENT.md](ONLINE-DEVELOPMENT.md) |
| Temporary online: Supabase (DB + storage) + Render (API + web) | PREPARED — REQUIRES EXTERNAL ACCOUNTS (free plans) | [SUPABASE.md](SUPABASE.md), [RENDER.md](RENDER.md), [CLOUDFLARE.md](CLOUDFLARE.md) |
| Production PC (Docker Compose + production overlay) | CI VERIFIED (rehearsed on every CI run) | [MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md) |

## What CI proves on every push

Job **Production overlay rehearsal** (`scripts/ci/rehearse-production.sh`):

1. Builds the images and starts `docker-compose.yml` + `docker-compose.production.yml`
   with a generated `.env` (random secrets, `APP_ENV=production`).
2. The API's entrypoint runs `python -m app.cli preflight` and refuses to start on
   configuration errors; `scripts/ops/verify.sh` runs `preflight --db`, a PostGIS
   distance check and readiness.
3. `scripts/deploy/smoke.sh` checks health, readiness, reference data, the Arabic
   RTL home page, the `/api/v1` proxy, security headers, search, map, that the
   jobs trigger is hidden, and that `/docs`, OpenAPI and dev tools are off.
4. Backup → `down -v` (all data destroyed) → restore → row counts and a media
   object are back.
5. Cloud → PC migration: a separate PostGIS server plays "Supabase", is migrated
   and seeded, exported data-only, imported into a fresh stack, verified.

## Configuration safety

`python -m app.cli preflight [--db]` (see `backend/app/core/preflight.py`):

| Level | Checks |
| --- | --- |
| error (any env) | AI provider without key, SMS http without gateway, SMTP without host, S3 without bucket |
| error (production) | `*` or non-https CORS origins, insecure cookies |
| warning (production) | http `FRONTEND_URL`, development DB password, rate limiting off, mock email, local storage, relaxed webhook SSRF guard, demo payments |
| `--db` | database reachable, PostGIS installed, migrations at head |

Other production defaults: `/docs` and OpenAPI disabled, dev tools (outbox
viewer) disabled, `JWT_SECRET` must be strong (startup fails otherwise), the API
port bound to `127.0.0.1`, demo payments refused unless
`PAYMENT_DEMO_IN_PRODUCTION=true`.

## Client IPs behind proxies

Rate limiting, audit logs and unique-visitor counts use the client IP.
`TRUSTED_PROXY_HOPS` is the number of proxies that append to
`X-Forwarded-For` in front of the API. The Next.js `/api/v1` proxy forwards
the header unchanged and does not count as a hop.

| Deployment | Value |
| --- | --- |
| Development (browser → Next.js proxy → API, no edge proxy) | `0` — the API uses the TCP peer (the frontend container); fine for one developer |
| PC behind Cloudflare Tunnel or Caddy | `1` (production overlay default) |
| Render (two hops, each Cloudflare + load balancer, plus the web egress) | `6` — measured live via `GET /api/v1/admin/system` → `request_network` (set in `render.yaml`) |

Never set it higher than reality: the extra entries would be client-controlled.

## Scheduled work

| Where | How |
| --- | --- |
| Compose (dev, PC) | `worker` service: Celery + embedded beat, `WORKER_BEAT=1`, one instance |
| Render free | `NOTIFICATIONS_INLINE=true` + GitHub workflow `scheduled-jobs.yml` → `POST /api/v1/internal/jobs/run` with `X-Jobs-Token` |

Both paths run the same functions (`backend/app/workers/registry.py`).
Manually: `python -m app.cli run-jobs [name …]`.

## Operations scripts

| Script | Purpose |
| --- | --- |
| `scripts/ops/backup.sh DIR` | data-only dump + Alembic revision + media archive + checksummed manifest |
| `scripts/ops/restore.sh DIR --yes` | recreate DB, migrate to the backup's revision, load, restore media, migrate to head, verify |
| `scripts/ops/export-cloud-db.sh DIR` | export a remote (Supabase) database, `SOURCE_DATABASE_URL` |
| `scripts/ops/import-cloud-db.sh DIR --yes` | import that export into the local stack (same revision required) |
| `scripts/ops/verify.sh` | PostGIS, counts, readiness, `preflight --db` |
| `scripts/deploy/smoke.sh WEB [API]` | post-deploy smoke test, any environment |
| `python -m app.cli storage-export/storage-import DIR` | copy media between the configured backend and a directory (idempotent) |

All Postgres client tools run in a `postgres:17` container, so nothing needs to
be installed on the host besides Docker.
