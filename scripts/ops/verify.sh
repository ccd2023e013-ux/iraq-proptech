#!/usr/bin/env bash
# Post-deployment / post-migration verification of a Compose deployment:
# PostGIS works, migrations are at head, configuration passes preflight,
# API and frontend answer. Prints key row counts for comparison with a manifest.
set -euo pipefail
cd "$(dirname "$0")/../.."
. scripts/ops/_lib.sh
DB_USER="${POSTGRES_USER:-proptech}"
DB_NAME="${POSTGRES_DB:-proptech}"
API="${API_URL:-http://localhost:8000}"
WEB="${WEB_URL:-http://localhost:3000}"

echo "PostGIS: $(pg_local psql -U "$DB_USER" -d "$DB_NAME" -Atc 'SELECT postgis_full_version()' | cut -c1-60)"
# A real spatial query: Basra Corniche ↔ Al-Ashar distance must be 2–3 km.
d=$(pg_local psql -U "$DB_USER" -d "$DB_NAME" -Atc \
  "SELECT round(ST_Distance(ST_SetSRID(ST_MakePoint(47.8417,30.5160),4326)::geography,
                            ST_SetSRID(ST_MakePoint(47.8160,30.5090),4326)::geography))")
[ "$d" -gt 2000 ] && [ "$d" -lt 3000 ] || die "spatial check failed ($d m)"
echo "Spatial check: ${d} m"

for t in users properties property_media crm_leads audit_logs; do
  echo "rows.$t: $(pg_local psql -U "$DB_USER" -d "$DB_NAME" -Atc "SELECT count(*) FROM $t")"
done

deadline=$((SECONDS + ${VERIFY_TIMEOUT:-180}))
until curl -fsS -o /dev/null "$API/api/v1/health/ready" && curl -fsS -o /dev/null "$WEB/"; do
  (( SECONDS < deadline )) || die "API/frontend did not become ready"
  sleep 3
done
compose exec -T backend python -m app.cli preflight --db
echo "VERIFY OK"
