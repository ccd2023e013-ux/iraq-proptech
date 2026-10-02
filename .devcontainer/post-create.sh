#!/usr/bin/env bash
# Runs once when the Codespace / dev container is created.
set -euo pipefail

echo "==> Installing PostgreSQL and Redis client tools"
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends postgresql-client redis-tools >/dev/null

echo "==> Backend: virtualenv + dependencies"
cd backend
python -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e ".[dev]"
cd ..

echo "==> Frontend: dependencies"
cd frontend
if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
cd ..

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from .env.example (edit it; never commit it)"
fi

echo "==> Waiting for PostGIS, then applying migrations"
for _ in $(seq 1 30); do
  pg_isready -h db -U proptech -d proptech >/dev/null 2>&1 && break
  sleep 2
done
(cd backend && .venv/bin/alembic upgrade head)

echo
echo "Ready. Common commands:  make help"
