# Iraq PropTech — منصة العقارات العراقية

An Arabic-first real-estate platform for Iraq (starting with Basra): listings,
map search on PostGIS, an agent CRM, and AI analysis that never invents
property facts.

> **Status:** Phase 1 — foundation. No real listings exist yet. See
> [docs/ROADMAP.md](docs/ROADMAP.md) for phase-by-phase progress.

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
.github/          CI: lint, types, tests on PostGIS, build, Docker smoke test
docker-compose*.yml  base · dev · production
```

The Celery worker shares the backend's code and image (`entrypoint.sh worker`),
so there is no separate `worker/` package: tasks use the same models and
services as the API without duplication.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Online development (Codespaces)](docs/ONLINE-DEVELOPMENT.md)
- [Roadmap & phase reports](docs/ROADMAP.md)
