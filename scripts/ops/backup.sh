#!/usr/bin/env bash
# Backup of the local (Docker Compose) deployment. Same format as
# export-cloud-db.sh, so one restore path serves both:
#   <dir>/alembic_revision.txt  schema version (the schema itself comes from migrations)
#   <dir>/data.dump             pg_dump custom format, DATA ONLY, schema `public`
#   <dir>/media.tar.gz          the media volume (photos, videos, private documents)
#   <dir>/manifest.txt          row counts and checksums
# Data-only avoids restoring PostGIS/TIGER extension internals, which do not
# round-trip cleanly between servers; migrations recreate an identical schema.
# Usage: scripts/ops/backup.sh [backups/<name>]
# Environment: COMPOSE_FILES="-f docker-compose.yml -f docker-compose.production.yml"
set -euo pipefail
cd "$(dirname "$0")/../.."
. scripts/ops/_lib.sh

OUT="${1:-backups/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"
DB_USER="${POSTGRES_USER:-proptech}"
DB_NAME="${POSTGRES_DB:-proptech}"
psql_local() { pg_local psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -Atc "$1"; }

echo "1/3 database → $OUT/data.dump"
psql_local 'SELECT version_num FROM alembic_version' > "$OUT/alembic_revision.txt"
pg_local pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --data-only --schema=public \
  --exclude-table=public.alembic_version --exclude-table=public.spatial_ref_sys > "$OUT/data.dump"

echo "2/3 media volume → $OUT/media.tar.gz"
compose run --rm --no-deps -T --entrypoint sh backend \
  -c 'tar -C /app/storage -czf - .' > "$OUT/media.tar.gz"

echo "3/3 manifest"
{
  echo "created_at: $(date -u +%FT%TZ)"
  echo "alembic: $(cat "$OUT/alembic_revision.txt")"
  for t in users properties property_media crm_leads audit_logs; do
    echo "rows.$t: $(psql_local "SELECT count(*) FROM $t")"
  done
  (cd "$OUT" && sha256sum data.dump media.tar.gz)
} > "$OUT/manifest.txt"
cat "$OUT/manifest.txt"
echo "Backup complete: $OUT (store .env separately — it holds the secrets)"
