#!/usr/bin/env bash
# Restore a backup made by backup.sh (replaces the current database and media):
#   1. recreate the database and migrate it to the backup's schema revision
#   2. load the data (import-cloud-db.sh) and the media volume
#   3. migrate to the current code's head (older backups are upgraded) and verify
# Usage: scripts/ops/restore.sh backups/<dir> --yes
set -euo pipefail
cd "$(dirname "$0")/../.."
. scripts/ops/_lib.sh

IN="${1:?usage: restore.sh <backup-dir> --yes}"
[ "${2:-}" = "--yes" ] || die "this replaces the current database and media; re-run with --yes"
[ -f "$IN/data.dump" ] && [ -f "$IN/media.tar.gz" ] || die "$IN is not a backup directory"
(cd "$IN" && grep -E ' (data.dump|media.tar.gz)$' manifest.txt | sha256sum -c -) \
  || die "checksum mismatch"
DB_USER="${POSTGRES_USER:-proptech}"
DB_NAME="${POSTGRES_DB:-proptech}"
REV="$(cat "$IN/alembic_revision.txt")"

echo "1/4 recreate database at revision $REV"
compose stop backend worker frontend >/dev/null 2>&1 || true
compose up -d db
# TCP check: a fresh volume first runs a temporary socket-only init server.
for _ in $(seq 1 90); do
  pg_local pg_isready -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  sleep 2
done
pg_local pg_isready -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" >/dev/null || die "database did not become ready"
pg_local psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE)" -c "CREATE DATABASE \"$DB_NAME\""
compose run --rm --no-deps -T --entrypoint alembic migrate upgrade "$REV"

echo "2/4 load data"
bash scripts/ops/import-cloud-db.sh "$IN" --yes --no-start

echo "3/4 restore media volume"
compose run --rm --no-deps -T --entrypoint sh backend \
  -c 'find /app/storage -mindepth 1 -delete && tar -C /app/storage -xzf -' < "$IN/media.tar.gz"

echo "4/4 migrate to head, start and verify"
compose run --rm --no-deps -T migrate
compose up -d
bash scripts/ops/verify.sh
