#!/usr/bin/env bash
# CI rehearsal of the production-PC runbook (docs/MIGRATE-TO-LOCAL-PC.md) on the
# real production Compose overlay:
#   A. start with production settings, preflight, deploy smoke test
#   B. backup → destroy everything (volumes too) → restore → verify (data + media)
#   C. cloud → PC: a separate PostGIS server plays "Supabase"; export data only,
#      import into a freshly migrated stack, verify counts match
set -euo pipefail
# Read the whole response: `grep -q` exits at the first match, which makes a
# still-streaming curl fail with exit 23 under pipefail.
grep_all() { grep "$@" >/dev/null; }
cd "$(dirname "$0")/../.."
export COMPOSE_FILES="-f docker-compose.yml -f docker-compose.production.yml"
. scripts/ops/_lib.sh
fail() { echo "REHEARSAL FAIL: $*"; exit 1; }
count() { pg_local psql -U proptech -d proptech -Atc "SELECT count(*) FROM $1"; }

cat > .env <<ENV
POSTGRES_PASSWORD=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)
CORS_ORIGINS=https://proptech.example
FRONTEND_URL=https://proptech.example
PAYMENT_DEMO_IN_PRODUCTION=true
ENV

echo "== A. production stack"
compose up -d db redis migrate backend worker frontend
VERIFY_TIMEOUT=240 bash scripts/ops/verify.sh
bash scripts/deploy/smoke.sh http://localhost:3000 http://localhost:8000
compose exec -T backend python -m app.cli seed-demo --listings 12 --allow-production
compose exec -T backend python -c "from app.storage import get_storage; \
get_storage().put('properties/rehearsal/photo.webp', b'RIFF-rehearsal', 'image/webp')"
props_before=$(count properties)
[ "$props_before" -ge 12 ] || fail "seed produced $props_before properties"

echo "== B. backup → destroy → restore"
bash scripts/ops/backup.sh backups/rehearsal
compose down -v
compose up -d db
bash scripts/ops/restore.sh backups/rehearsal --yes
[ "$(count properties)" = "$props_before" ] || fail "properties after restore: $(count properties)"
compose exec -T backend python -c "from app.storage import get_storage; \
assert get_storage().get('properties/rehearsal/photo.webp') == b'RIFF-rehearsal'"
echo "restore verified: $props_before properties + media object"

echo "== C. cloud database → PC"
docker rm -f cloud-db >/dev/null 2>&1 || true
docker run -d --name cloud-db -p 55432:5432 -e POSTGRES_PASSWORD=cloudpw \
  -e POSTGRES_DB=postgres postgis/postgis:16-3.4 >/dev/null
until docker exec cloud-db pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; do sleep 2; done
sleep 3
CLOUD="postgresql://postgres:cloudpw@localhost:55432/postgres"
image="proptech-backend"  # built by `docker compose build` (project "proptech")
docker run --rm --network host -e DATABASE_URL="$CLOUD" -e PREFLIGHT=0 "$image" migrate
docker run --rm --network host -e DATABASE_URL="$CLOUD" "$image" \
  python -m app.cli seed-demo --listings 7
cloud_props=$(docker exec cloud-db psql -U postgres -Atc "SELECT count(*) FROM properties")
SOURCE_DATABASE_URL="$CLOUD" bash scripts/ops/export-cloud-db.sh migration

compose down -v
compose up -d db redis migrate backend worker frontend
VERIFY_TIMEOUT=240 bash scripts/ops/verify.sh
bash scripts/ops/import-cloud-db.sh migration --yes
[ "$(count properties)" = "$cloud_props" ] || fail "imported $(count properties) of $cloud_props properties"
[ "$(count governorates)" = "19" ] || fail "governorates after import"
pg_local psql -U proptech -d proptech -Atc \
  "SELECT count(*) FROM properties WHERE search_vector IS NOT NULL" | grep -qx "$cloud_props" \
  || fail "generated search columns not rebuilt"
VERIFY_TIMEOUT=240 bash scripts/ops/verify.sh
bash scripts/deploy/smoke.sh http://localhost:3000 http://localhost:8000
echo "REHEARSAL OK: production overlay, backup/restore and cloud→PC migration"
