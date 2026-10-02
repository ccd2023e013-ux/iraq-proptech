#!/usr/bin/env bash
# Export the temporary cloud database (e.g. Supabase) for the move to the PC.
# DATA ONLY from the `public` schema: the PC recreates the schema with its own
# migrations, so provider-specific schemas/extension layouts never come along.
# Usage: SOURCE_DATABASE_URL='postgresql://user:pass@host:5432/postgres?sslmode=require' \
#          scripts/ops/export-cloud-db.sh migration/
set -euo pipefail
cd "$(dirname "$0")/../.."
. scripts/ops/_lib.sh
: "${SOURCE_DATABASE_URL:?set SOURCE_DATABASE_URL (libpq URL, not postgresql+psycopg)}"
OUT="${1:-migration}"
mkdir -p "$OUT"
URL="${SOURCE_DATABASE_URL/postgresql+psycopg:/postgresql:}"

pg_client psql "$URL" -Atc 'SELECT version_num FROM public.alembic_version' > "$OUT/alembic_revision.txt"
pg_client pg_dump "$URL" -Fc --data-only --schema=public \
  --exclude-table=public.alembic_version --exclude-table=public.spatial_ref_sys \
  -f "/work/$OUT/data.dump"
pg_client psql "$URL" -Atc "SELECT 'rows.'||relname||': '||n_live_tup FROM pg_stat_user_tables
  WHERE schemaname='public' ORDER BY relname" > "$OUT/source_counts.txt" || true
echo "Exported to $OUT (revision $(cat "$OUT/alembic_revision.txt"))"
