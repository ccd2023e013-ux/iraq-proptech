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

The browser calls the frontend's own origin; `app/api/[...path]/route.ts`
forwards `/api/v1/*` to `API_INTERNAL_URL` at runtime. This removes CORS from
the default setup and works behind Codespaces port forwarding. Setting
`NEXT_PUBLIC_API_URL` switches the browser to calling the API directly.

## Backend layout

```
app/
  main.py            app factory: middleware, error handlers, routers
  api.py             /api/v1 router aggregation
  core/              settings, JSON logging, error envelope, middleware
  db/                declarative base + mixins, engine/session, model registry
  system/            health/readiness, system_settings
  workers/           Celery app and tasks
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
- **Migrations:** a test fails if models and migrations drift apart, and every
  migration must downgrade cleanly.

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
