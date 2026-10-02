#!/usr/bin/env bash
# Import a data-only export (export-cloud-db.sh) into the local Compose database.
# The local schema must be migrated to the SAME Alembic revision first; the
# reference rows seeded by migrations are replaced by the exported ones.
# Usage: scripts/ops/import-cloud-db.sh migration/ --yes [--no-start]
set -euo pipefail
cd "$(dirname "$0")/../.."
. scripts/ops/_lib.sh
IN="${1:?usage: import-cloud-db.sh <export-dir> --yes}"
[ "${2:-}" = "--yes" ] || die "this replaces all application data; re-run with --yes"
DB_USER="${POSTGRES_USER:-proptech}"
DB_NAME="${POSTGRES_DB:-proptech}"
psql_local() { pg_local psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 "$@"; }

want="$(cat "$IN/alembic_revision.txt")"
have="$(psql_local -Atc 'SELECT version_num FROM alembic_version' 2>/dev/null || true)"
[ "$want" = "$have" ] || die "local schema is at '$have' but the export is from '$want' — run the matching migrations first"

compose stop backend worker >/dev/null 2>&1 || true
echo "Emptying application tables (schema kept)…"
psql_local -Atc "SELECT string_agg(format('%I.%I', schemaname, tablename), ', ')
  FROM pg_tables WHERE schemaname='public'
  AND tablename NOT IN ('alembic_version','spatial_ref_sys')" > /tmp/tables.txt
psql_local -c "TRUNCATE $(cat /tmp/tables.txt) RESTART IDENTITY CASCADE"
echo "Loading data…"
PG_NET_MOUNT="$(cd "$IN" && pwd)" pg_net pg_restore --dbname "${POSTGRES_DB:-proptech}" --data-only --disable-triggers \
  --single-transaction --exit-on-error /in/data.dump
if [ "${3:-}" != "--no-start" ]; then compose up -d; fi
echo "Imported. Next: scripts/ops/verify.sh, then copy media (docs/MIGRATE-TO-LOCAL-PC.md)."
