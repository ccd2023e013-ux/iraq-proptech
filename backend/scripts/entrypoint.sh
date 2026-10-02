#!/bin/sh
# Container entrypoint. Roles: api | worker | migrate | <any command>.
# PORT is honoured so the same image runs on any host that injects it.
set -eu

role="${1:-api}"

case "$role" in
  api)
    if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
      alembic upgrade head
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
      --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
    ;;
  worker)
    exec celery -A app.workers.celery_app worker --loglevel="${LOG_LEVEL:-INFO}" \
      --concurrency="${WORKER_CONCURRENCY:-2}"
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    exec "$@"
    ;;
esac
