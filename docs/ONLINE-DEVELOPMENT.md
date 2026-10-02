# Online development (GitHub Codespaces) — $0

The whole platform can be developed from a browser. Nothing needs to be
installed on a personal computer.

## Cost

GitHub's free plan includes a monthly Codespaces allowance (core-hours and
storage). A 2-core codespace is enough for this project. To stay at $0:

- Leave the **spending limit at $0** (the default) under
  *Settings → Billing → Codespaces*. GitHub then stops codespaces instead of
  charging.
- Stop the codespace when you finish (*Codespaces → … → Stop*); idle ones stop
  automatically after 30 minutes by default.
- Delete codespaces you no longer need — stored codespaces count against the
  free storage quota.

Check the current quota on GitHub's billing page; it can change over time.

## What the codespace contains

Defined in `.devcontainer/`:

| Container | Purpose |
| --- | --- |
| `workspace` | Python 3.12, Node.js 22, git, GitHub CLI, psql, redis-cli |
| `db` | `postgis/postgis:16-3.4` — the same image as production |
| `redis` | `redis:7-alpine` |

On creation, `post-create.sh` creates `backend/.venv`, installs backend and
frontend dependencies, copies `.env.example` to `.env`, and runs migrations.

## Daily workflow

```bash
make api      # terminal 1 — FastAPI on :8000 (open /docs)
make web      # terminal 2 — Next.js on :3000 (Ports tab → open in browser)
make worker   # optional — Celery worker
make test     # run all tests
```

The browser only talks to port 3000; the frontend proxies `/api/v1/*` to the
API on :8000, so port 8000 can stay private.

Useful:

```bash
psql postgresql://proptech:proptech@db:5432/proptech   # database shell
redis-cli -h redis ping
```

## Continuous integration

Every push to GitHub runs `.github/workflows/ci.yml`:

1. Backend: ruff, mypy, pytest against a real PostGIS service.
2. Frontend: eslint, prettier, vitest, `next build`, `tsc`.
3. Docker: builds all images, starts the full stack with Compose, and checks
   API readiness, the frontend proxy, the Arabic RTL page, and a Celery task
   round-trip through Redis.

Public repositories get unlimited free Actions minutes; private ones get a
free monthly allowance that this pipeline uses only a small part of.
