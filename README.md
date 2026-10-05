# Iraq PropTech — منصة العقارات العراقية

An Arabic-first real-estate platform for Iraq (starting with Basra): listings,
map search on PostGIS, an agent CRM, and AI analysis that never invents
property facts.

> **Live (free tier, DEMO data):** <https://iraq-proptech-web.onrender.com>
> · API <https://iraq-proptech-api.onrender.com/api/v1/health> — verification
> status in [docs/ONLINE-LAUNCH-STATUS.md](docs/ONLINE-LAUNCH-STATUS.md). The first
> visit after idle time can take up to a minute (free instances sleep).
>
> **Status:** all build phases (1–12) complete and CI verified, plus a final
> security audit and an automated 16-step acceptance scenario. Demo data only;
> no real listings yet. Checkpoints: [docs/PHASE-STATUS.md](docs/PHASE-STATUS.md).

## What it does

- **Listings** for houses, apartments, land, commercial units — Arabic first,
  photos/videos/private documents, verification, moderation, featured
  promotions.
- **Search** with Arabic spelling normalisation, filters, saved-search alerts,
  favorites, comparison, and **natural-language search** ("بيت للبيع في البصرة").
- **Maps** (MapLibre + PostGIS): clustering, boundaries, nearby places, location
  privacy (approximate public locations).
- **Agencies and agents** with invitations; **CRM**: inquiries → leads,
  pipeline, activities, tasks, appointments, conversations.
- **AI** (mock by default, Claude/OpenAI/Gemini with a key): price analysis,
  summaries, listing quality, duplicate/risk signals, reply drafts — every
  answer shows its method, sources and limits.
- **Admin**: moderation queues, reports, users and roles, audit log, settings,
  webhooks, jobs, analytics, billing (DEMO payment mode — no money moves).
- **Notifications**: in-app, email, SMS (mock), web push, signed webhooks (n8n).

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic 2 |
| Database | PostgreSQL 16 + PostGIS 3.4 (+ `pg_trgm`) |
| Jobs | Celery on Redis |
| Frontend | Next.js 15 (App Router) · TypeScript · Tailwind CSS 4 · Arabic RTL first |
| Automation | n8n (optional, never required by the app) |
| Packaging | Docker images + Docker Compose (dev / production overlays) |

Everything runs at **$0**: no paid service or API key is required. AI, email,
SMS and payments use clearly labelled MOCK providers until configured.

## Run it

### In the browser (GitHub Codespaces) — recommended for now

1. On GitHub: **Code → Codespaces → Create codespace on main**.
2. Wait for setup to finish (installs dependencies and runs migrations).
3. In two terminals:
   ```bash
   make api    # FastAPI on :8000  → /docs for the OpenAPI UI
   make web    # Next.js on :3000  → opens in the Ports tab
   ```

Details: [docs/ONLINE-DEVELOPMENT.md](docs/ONLINE-DEVELOPMENT.md).

### With Docker (any machine, including the future production PC)

```bash
cp .env.example .env
docker compose up --build          # production-like images
make up                             # dev mode with hot reload
```

Frontend: http://localhost:3000 · API: http://localhost:8000/docs

## Common commands

```bash
make help          # list everything
make test          # backend (pytest on real PostGIS) + frontend (vitest)
make lint          # ruff, mypy, eslint, tsc, prettier
make migrate       # alembic upgrade head
make migration m="add properties"
```

## Repository layout

```
backend/          FastAPI app, domain modules, Alembic migrations, Celery worker
frontend/         Next.js app (feature-based folders, i18n, design system)
docs/             Architecture, development, deployment and migration guides
.devcontainer/    Reproducible Codespaces environment (PostGIS + Redis included)
.github/          CI: lint, types, tests on PostGIS, build, Docker smoke + E2E, production rehearsal
scripts/          CI smoke/E2E, deploy smoke test, ops (backup, restore, cloud→PC migration)
docker-compose*.yml  base · dev · production
```

The Celery worker shares the backend's code and image (`entrypoint.sh worker`),
so there is no separate `worker/` package: tasks use the same models and
services as the API without duplication.

## Documentation

| Topic | Docs |
| --- | --- |
| Overview | [Architecture](docs/ARCHITECTURE.md) · [Data model](docs/DATA_MODEL.md) · [API](docs/API.md) · [Roadmap](docs/ROADMAP.md) · [Phase status](docs/PHASE-STATUS.md) · [Changelog](CHANGELOG.md) |
| Domain | [Authentication](docs/AUTHENTICATION.md) · [RBAC](docs/RBAC.md) · [GIS](docs/GIS.md) · [CRM](docs/CRM.md) · [AI](docs/AI.md) · [Automation](docs/AUTOMATION.md) · [Analytics](docs/ANALYTICS.md) · [Monetization](docs/MONETIZATION.md) |
| Running | [Development](docs/DEVELOPMENT.md) · [Online development](docs/ONLINE-DEVELOPMENT.md) · [Deployment](docs/DEPLOYMENT.md) · [Supabase](docs/SUPABASE.md) · [Render](docs/RENDER.md) · [Cloudflare](docs/CLOUDFLARE.md) · [Migrate to the PC](docs/MIGRATE-TO-LOCAL-PC.md) |
| Security | [Security model and audit](docs/SECURITY.md) |
