# Architecture

## Principles

1. **Modular monolith, API-first.** One FastAPI service organised by domain
   (`app/<domain>/{models,schemas,service,router}.py`). Domains talk through
   Python services, not HTTP, so any domain can be split out later.
2. **PostgreSQL is the source of truth.** Workers and n8n read/write through the
   API or the same service layer; they never own business state.
3. **Portable by construction.** Configuration only via environment variables;
   standard PostgreSQL + PostGIS features only; the same Docker images run in
   Codespaces, on temporary free hosts, and on the production PC.
4. **No vendor lock-in.** AI, storage, maps, email, SMS, WhatsApp, payments and
   analytics sit behind interfaces with a MOCK/local default.
5. **Never invent facts.** AI output is validated, versioned, logged, and must
   label inference and missing data explicitly.

## Runtime topology

```
Browser ──► Next.js (3000) ──/api/v1/* proxy──► FastAPI (8000) ──► PostgreSQL + PostGIS
                                                    │                  ▲
                                                    └──► Redis ◄── Celery worker
                                                               (n8n ◄─► webhooks, optional)
```

Deployment variants of the same images (see [DEPLOYMENT.md](DEPLOYMENT.md)):

| Variant | Differences |
| --- | --- |
| Compose (dev, production PC) | as drawn; production overlay binds the API to 127.0.0.1, one TLS proxy/tunnel in front of :3000 |
| Render + Supabase (temporary) | no Redis/worker: notifications delivered inline after commit, scheduled jobs via a token-protected endpoint called by a GitHub cron; media in an S3 bucket |

The browser calls the frontend's own origin; `app/api/[...path]/route.ts`
forwards `/api/v1/*` to `API_INTERNAL_URL` at runtime. This removes CORS from
the default setup and works behind Codespaces port forwarding. Setting
`NEXT_PUBLIC_API_URL` switches the browser to calling the API directly.

## Backend layout

```
app/
  main.py            app factory: middleware, error handlers, routers
  api.py             /api/v1 router aggregation
  cli.py             operator CLI: create-superadmin, seed-demo, preflight, run-jobs, storage-export/import
  policies.py        object-level authorization rules
  storage.py         media storage (local filesystem | S3-compatible)
  core/              settings, JSON logging, errors, middleware, rate limits, client IP, preflight
  db/                declarative base + mixins, engine/session, model registry
  auth/ users/ rbac/ audit/          identity, sessions, roles, audit log
  agencies/ properties/ geo/ map/    listings, media, locations, PostGIS
  search/ favorites.py money.py      search, saved searches, exchange rates
  crm/ notifications/ moderation/    leads, messaging, notifications/webhooks, reports
  ai/ analytics/ billing/            AI providers, aggregates, plans/payments (DEMO)
  system/            health/readiness, settings, dev outbox, internal jobs trigger
  workers/           Celery app, beat schedule, job registry
alembic/             migrations (plain PostgreSQL/PostGIS DDL)
tests/               pytest — db tests run against real PostGIS
```

### Cross-cutting conventions

- **Errors:** every error is `{"error": {"code", "message", "details?", "request_id"}}`.
  `code` is stable; the frontend maps it to Arabic/English text.
- **Logging:** one JSON line per request with `request_id`, method, path (no
  query string), status, duration. Secret-looking keys are redacted.
- **Request IDs:** accepted from `X-Request-ID` if well-formed, otherwise
  generated, and echoed on every response.
- **Database:** UUID primary keys (`gen_random_uuid()` server default), tz-aware
  timestamps, deterministic constraint names, soft delete where history matters.
- **Migrations:** a test fails if models and migrations drift apart, if a
  foreign key lacks an index, or if a migration does not downgrade cleanly.
- **Domain events:** services emit events (`app/events.py`); handlers run in
  the caller's transaction inside a savepoint (a failing handler never breaks
  the operation), and external side effects (email, SMS, webhooks) go through
  an outbox delivered after commit.

## Frontend layout

```
src/
  app/          routes (App Router), API proxy route, error/404 pages
  components/   design system (ui/) and layout
  features/     feature modules (system, properties, map, crm, ...)
  i18n/         Arabic (default, RTL) + English dictionaries
  lib/          API client, config
  types/        API types
```

Arabic is the default locale (`<html lang="ar" dir="rtl">`); English is chosen
by cookie or `Accept-Language`. Styling uses logical properties (`ms-`, `ps-`,
`border-s`) so layouts mirror correctly.
