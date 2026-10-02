#!/bin/sh
# Container entrypoint. Roles: api | worker | migrate | <any command>.
# PORT is honoured so the same image runs on any host that injects it.
set -eu

role="${1:-api}"

case "$role" in
  api)
    # Refuse to start with unsafe or incomplete configuration (errors only matter
    # in production; warnings are printed). PREFLIGHT=0 skips it.
    if [ "${PREFLIGHT:-1}" = "1" ]; then
      python -m app.cli preflight
    fi
    if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
      alembic upgrade head
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
      --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
    ;;
  worker)
    # WORKER_BEAT=1 (default) embeds the scheduler; run exactly one such worker.
    beat=""
    if [ "${WORKER_BEAT:-1}" = "1" ]; then
      beat="--beat --schedule=/tmp/celerybeat-schedule"
    fi
    # shellcheck disable=SC2086
    exec celery -A app.workers.celery_app worker --loglevel="${LOG_LEVEL:-INFO}" \
      --concurrency="${WORKER_CONCURRENCY:-2}" $beat
    ;;
  beat)
    exec celery -A app.workers.celery_app beat --loglevel="${LOG_LEVEL:-INFO}" \
      --schedule=/tmp/celerybeat-schedule
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    exec "$@"
    ;;
esac
