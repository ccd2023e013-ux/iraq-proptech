# Supabase (temporary database + storage)

Supabase is **temporary development infrastructure**. The application uses
it as plain PostgreSQL + PostGIS and as an S3-compatible bucket; no Supabase
SDK, auth, RLS policies or proprietary feature is used, so the move to the
production PC (see [MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md)) needs no
code change.

Status: **prepared, not deployed** — creating the project requires the
owner's Supabase account (free plan, no card).

## 1. Create the project

1. <https://supabase.com> → New project (Free plan). Choose a region close to
   Iraq (e.g. Frankfurt) and a strong database password.
2. **Database → Extensions**: enable `postgis` and `pg_trgm`. (Migration
   `0001` also runs `CREATE EXTENSION IF NOT EXISTS`, which works when the role
   is allowed to; enabling them in the dashboard first avoids permission
   surprises.)

## 2. Connection string

Free projects' *direct* host (`db.<ref>.supabase.co`) is IPv6-only, and Render
has no IPv6 egress. Use the **Supavisor session pooler** (IPv4):

```
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

- Session mode (port **5432**) is recommended.
- Transaction mode (port **6543**) also works: the API auto-detects it and
  disables server-side prepared statements
  (`DB_PREPARED_STATEMENTS`, see `backend/app/core/config.py`).
- Keep `DB_POOL_SIZE` small on the free plan (`DB_POOL_SIZE=3`,
  `DB_MAX_OVERFLOW=2`).

## 3. Schema

Migrations run automatically on Render (`RUN_MIGRATIONS=1`). Manually from a
Codespace:

```bash
cd backend
DATABASE_URL='<url above>' .venv/bin/alembic upgrade head
DATABASE_URL='<url above>' .venv/bin/python -m app.cli preflight --db
```

Optional demo content (clearly labelled DEMO): `python -m app.cli seed-demo`
(production refuses it unless `--allow-production`).

Migrations are standard Alembic/PostgreSQL. The model–migration drift test
ignores Supabase's own schemas (`auth`, `storage`, `realtime`, `vault`,
`extensions`), so their presence never affects our schema.

## 4. Storage (media and private documents)

Render's container disk is ephemeral, so uploads must go to a bucket:

1. **Storage → New bucket** `media`, **private** (the API streams files and
   enforces authorization; never make it public).
2. **Storage → Settings → S3 Connection**: enable, note the endpoint and
   region, and create an access key.
3. Configure the API:

```
STORAGE_BACKEND=s3
S3_BUCKET=media
S3_ENDPOINT_URL=https://<ref>.supabase.co/storage/v1/s3
S3_REGION=<region shown on that page>
S3_ACCESS_KEY_ID=…
S3_SECRET_ACCESS_KEY=…
```

The client uses path-style addressing, which Supabase, MinIO and R2 all
accept. The storage layer is tested against an in-process S3 implementation
(`backend/tests/test_storage.py`).

## Free-plan limits to keep in mind

| Limit (free plan, may change — check Supabase's pricing page) | Effect |
| --- | --- |
| Project pauses after a period of inactivity | First request after a pause fails until the project is resumed in the dashboard |
| Database and storage size caps | Enough for development; demo data is small |
| No point-in-time recovery | Take exports with `scripts/ops/export-cloud-db.sh` |

Never enable paid add-ons or a spend cap override.

## Exporting (before moving to the PC)

```bash
SOURCE_DATABASE_URL='postgresql://postgres.<ref>:<password>@…:5432/postgres?sslmode=require' \
  scripts/ops/export-cloud-db.sh migration/
```

This writes a data-only dump of the `public` schema plus the Alembic revision.
The PC recreates the schema from migrations, so Supabase's extension layout
never comes along. Media: `python -m app.cli storage-export <dir>` with the
Supabase S3 settings. Full procedure: [MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md).
