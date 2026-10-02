#!/usr/bin/env bash
# Backup → restore verification of the LIVE database without touching it:
#   1. exact row counts on the live database (read-only)
#   2. scripts/ops/export-cloud-db.sh (the documented backup)
#   3. a fresh production-overlay stack on this runner, migrated to the same revision
#   4. scripts/ops/import-cloud-db.sh (the documented restore), then compare counts,
#      PostGIS, Arabic search through the restored API, deploy smoke test
#   5. optional media: copy the Supabase bucket into the stack when S3 secrets exist
# Usage: SOURCE_DATABASE_URL=… scripts/live/backup_restore.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
export COMPOSE_FILES="-f docker-compose.yml -f docker-compose.production.yml"
. scripts/ops/_lib.sh
: "${SOURCE_DATABASE_URL:?}"
URL="${SOURCE_DATABASE_URL/postgresql+psycopg:/postgresql:}"
fail() { echo "BACKUP/RESTORE FAIL: $*" >&2; exit 1; }
TABLES="users properties property_media districts agencies points_of_interest crm_leads"
counts_sql="SELECT $(for t in $TABLES; do printf "'%s='||(SELECT count(*) FROM public.%s)||' '||" "$t" "$t"; done) ''"

echo "1. live row counts (read-only)"
before=$(pg_client psql "$URL" -Atc "$counts_sql")
echo "   $before"

echo "2. backup (data-only export + revision)"
rm -rf live-backup
bash scripts/ops/export-cloud-db.sh live-backup
ls -l live-backup
after=$(pg_client psql "$URL" -Atc "$counts_sql")
[ "$before" = "$after" ] || echo "   (live data changed during the export: $after)"

echo "3. fresh production stack"
cat > .env <<ENV
POSTGRES_PASSWORD=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)
CORS_ORIGINS=https://restore-check.example
FRONTEND_URL=https://restore-check.example
PAYMENT_DEMO_IN_PRODUCTION=true
ENV
compose up -d db redis migrate backend frontend
VERIFY_TIMEOUT=300 bash scripts/ops/verify.sh

echo "4. restore and compare"
bash scripts/ops/import-cloud-db.sh live-backup --yes
restored=$(pg_local psql -U proptech -d proptech -Atc "$counts_sql")
echo "   live:     $before"
echo "   restored: $restored"
[ "$restored" = "$before" ] || [ "$restored" = "$after" ] || fail "row counts differ"
pg_local psql -U proptech -d proptech -Atc \
  "SELECT count(*) FROM properties WHERE is_demo AND search_vector IS NOT NULL AND display_location IS NOT NULL" \
  | awk '{ if ($1 < 100) exit 1 }' || fail "restored listings lack search vectors/geometry"
compose up -d
VERIFY_TIMEOUT=300 bash scripts/ops/verify.sh
q=$(python3 -c "import urllib.parse; print(urllib.parse.quote('بيت للبيع في البصرة'))")
curl -fsS "http://localhost:3000/api/v1/ai/search?q=$q" | jq -e '.total > 0' >/dev/null \
  || fail "Arabic search on the restored copy"
bash scripts/deploy/smoke.sh http://localhost:3000 http://localhost:8000

media="not checked (S3 secrets not provided to GitHub)"
if [ -n "${S3_ACCESS_KEY_ID:-}" ] && [ -n "${S3_SECRET_ACCESS_KEY:-}" ] && [ -n "${S3_ENDPOINT_URL:-}" ]; then
  echo "5. media: bucket → stack volume"
  out=$(compose run --rm --no-deps -T -e STORAGE_BACKEND=s3 -e S3_BUCKET="${S3_BUCKET:-media}" \
    -e S3_ENDPOINT_URL -e S3_REGION -e S3_ACCESS_KEY_ID -e S3_SECRET_ACCESS_KEY \
    backend python -m app.cli storage-export /app/storage)
  echo "   $out"
  media="copied: $out"
fi

summary="restored from a fresh export of the live database: $restored; media $media"
echo "::notice title=live backup restore summary::$summary"
echo "BACKUP/RESTORE OK"
