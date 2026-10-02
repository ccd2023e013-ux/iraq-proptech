# Migrating to the production PC

The temporary cloud stack (Supabase + Render) and the production PC run the
**same code and the same Docker images**. Moving is a data move plus
configuration — no application change.

| Temporary | Production PC | How it moves |
| --- | --- | --- |
| Supabase PostgreSQL + PostGIS | `db` service (`postgis/postgis:16-3.4`) | data-only export → import into a migrated schema |
| Supabase Storage (S3) | `media` Docker volume (or MinIO/any S3) | `app.cli storage-export` |
| Render API | `backend` service | same image |
| Render web | `frontend` service | same image |
| — (inline notifications, GitHub cron) | `redis` + `worker` (Celery + beat) | enabled by default in Compose |
| — (optional cloud n8n) | `n8n` service (`--profile automation`) | re-create the webhook in Admin → Webhooks |

The whole runbook below is rehearsed on every CI run by
`scripts/ci/rehearse-production.sh` (job *Production overlay rehearsal*):
production overlay start, preflight, deploy smoke test, backup → destroy →
restore, and a cloud → PC data migration from a separate PostGIS server.

## 1. Prepare the PC

- Docker Engine / Docker Desktop with Compose **≥ 2.24**, ≥ 8 GB RAM for
  Docker, ~20 GB disk.
- `git clone https://github.com/ccd2023e013-ux/iraq-proptech && cd iraq-proptech`
- Create `.env` (never commit it):

```bash
cp .env.example .env
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env
```

  then edit `.env`:

| Variable | Production value |
| --- | --- |
| `APP_ENV` | set by the production overlay (`production`) |
| `FRONTEND_URL`, `CORS_ORIGINS` | your public https origin, e.g. `https://aqar.example.iq` |
| `TRUSTED_PROXY_HOPS` | `1` (one TLS proxy/tunnel in front of the frontend) — overlay default |
| `STORAGE_BACKEND` | `local` (named volume `media`) or `s3` for MinIO/R2 |
| `EMAIL_PROVIDER`, `SMTP_*` | real SMTP for verification/reset emails (else they are only logged) |
| `AI_PROVIDER` + key | optional; `mock` works offline |
| `PAYMENT_PROVIDER` | `none` until a real gateway adapter exists (demo is refused in production unless `PAYMENT_DEMO_IN_PRODUCTION=true`) |
| `JOBS_TRIGGER_TOKEN` | leave unset — Celery beat runs the jobs |

All variables: [ENVIRONMENT](../.env.example) and `backend/app/core/config.py`.

## 2. Start an empty stack and verify it

```bash
export COMPOSE_FILES="-f docker-compose.yml -f docker-compose.production.yml"
docker compose $COMPOSE_FILES build
docker compose $COMPOSE_FILES up -d
scripts/ops/verify.sh          # PostGIS spatial check, row counts, preflight --db, readiness
scripts/deploy/smoke.sh http://localhost:3000 http://localhost:8000
```

The API listens on `127.0.0.1:8000` only; the public entry point is the
frontend on `:3000`, which proxies `/api/v1/*`. The API refuses to start when
the preflight finds configuration errors.

## 3. Move the data

### 3.1 Database (Supabase → PC)

```bash
# 1. On any machine with Docker: export (data only, public schema + revision)
SOURCE_DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require' \
  scripts/ops/export-cloud-db.sh migration/

# 2. On the PC: the local schema must be at the same revision as the export.
cat migration/alembic_revision.txt
docker compose $COMPOSE_FILES run --rm --entrypoint alembic migrate current
#    (check out the same git commit that the cloud ran if they differ)

# 3. Import (replaces the reference rows the migrations seeded), then verify
scripts/ops/import-cloud-db.sh migration/ --yes
scripts/ops/verify.sh
```

Why data-only: Supabase installs extensions in its own schema layout; the
PC's schema is created by our migrations, so nothing provider-specific is
copied. Generated search columns are rebuilt by PostgreSQL on import, and
sequences (listing reference numbers) are carried over.

### 3.2 Media (Supabase Storage → PC)

```bash
# Export with the *cloud* storage settings (from Render's environment):
docker compose $COMPOSE_FILES run --rm --no-deps \
  -e STORAGE_BACKEND=s3 -e S3_BUCKET=media -e S3_ENDPOINT_URL=https://<ref>.supabase.co/storage/v1/s3 \
  -e S3_REGION=<region> -e S3_ACCESS_KEY_ID=… -e S3_SECRET_ACCESS_KEY=… \
  backend python -m app.cli storage-export /app/storage
```

This writes straight into the `media` volume (the default local storage).
The copy is idempotent — re-run it after a final cut-over to pick up late
uploads. To keep using a bucket instead (MinIO on the PC, R2), point
`STORAGE_BACKEND=s3` at it and use `storage-import`.

### 3.3 Redis, worker, scheduled jobs

Nothing to migrate: Redis holds only rate-limit windows and the job queue.
The `worker` service runs Celery with the beat scheduler embedded
(`WORKER_BEAT=1`, exactly one worker). Disable the GitHub workflow
*Scheduled jobs* (or delete its secrets) once the PC is live, and set
`NOTIFICATIONS_INLINE=false` (default).

### 3.4 n8n (optional)

```bash
docker compose $COMPOSE_FILES --profile automation up -d n8n
```

Create the workflow in n8n, then in **Admin → Webhooks** add its URL
(`http://n8n:5678/webhook/...`). Private Docker hosts need
`WEBHOOK_ALLOW_HTTP=true` and `WEBHOOK_ALLOW_PRIVATE_HOSTS=true` — only for
this internal network. The platform keeps working when n8n is down
(deliveries are retried and visible in the admin). See
[AUTOMATION.md](AUTOMATION.md).

## 4. Publish safely

Never expose PostgreSQL, Redis, n8n or the API port to the internet. Put one
TLS-terminating proxy in front of the frontend:

- **Cloudflare Tunnel** (free, no open router ports):
  `cloudflared tunnel --url http://localhost:3000`, or a named tunnel with
  your domain.
- **Caddy** on the PC with automatic HTTPS:
  `aqar.example.iq { reverse_proxy localhost:3000 }`.

Both append the client address to `X-Forwarded-For`, which is why
`TRUSTED_PROXY_HOPS=1`. If you add another proxy layer, increase it; never set
it higher than the real number of proxies (clients could then spoof their
address).

## 5. Cut-over checklist

1. Announce a short maintenance window; stop writes on the cloud site (scale
   the Render API to 0 or put the frontend in maintenance).
2. Final `export-cloud-db.sh` and `storage-export`; import on the PC.
3. `scripts/ops/verify.sh` — compare row counts with `migration/source_counts.txt`.
4. `scripts/deploy/smoke.sh https://<domain>` through the public URL.
5. Point DNS / the tunnel at the PC. Update `FRONTEND_URL`/`CORS_ORIGINS` if
   the domain changed.
6. Keep the cloud project read-only for a week before deleting it.

## 6. Backups on the PC

```bash
scripts/ops/backup.sh backups/$(date +%F)        # data + media + manifest (checksums)
scripts/ops/restore.sh backups/2026-10-03 --yes   # rebuild schema at the backup's revision, load, migrate to head
```

Schedule `backup.sh` daily (cron / Windows Task Scheduler with WSL) and copy
`backups/` and `.env` to another disk or an encrypted cloud drive. Backups are
data-only by design: the schema comes from the migrations at the recorded
revision, so a restore also works after upgrading the code (it migrates
forward after loading).

## 7. Rollback plan

| Situation | Action |
| --- | --- |
| PC stack misbehaves right after cut-over | Point DNS/tunnel back to Render (the cloud stack was kept read-only and unchanged); investigate at leisure |
| Bad deploy on the PC | `git checkout <previous commit>`, `docker compose $COMPOSE_FILES up -d --build`; if a migration ran, restore the backup taken before the deploy with `restore.sh` |
| Data corruption / operator error | `scripts/ops/restore.sh backups/<last good> --yes` |
| Disk failure | New disk/PC → sections 1–2 → `restore.sh` from the off-machine copy |

Always run `backup.sh` before `git pull` + rebuild.

## 8. Optional GPU workloads

Nothing in the platform needs a GPU. A local AI model can be added later as
another provider behind `AI_PROVIDER` (see [AI.md](AI.md)); run it as an
extra Compose service with GPU access on the PC, reachable only on the
internal network.
