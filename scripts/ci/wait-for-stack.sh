#!/usr/bin/env bash
# Start the Docker Compose stack and wait until the API is ready and the
# frontend answers. Used by CI; handy locally too.
set -euo pipefail

TIMEOUT="${STACK_TIMEOUT:-240}"
API="${API_URL:-http://localhost:8000}"
WEB="${WEB_URL:-http://localhost:3000}"

docker compose up -d db redis backend worker frontend

wait_for() {
  local name="$1" url="$2" deadline=$((SECONDS + TIMEOUT))
  until curl -fsS -o /dev/null "$url"; do
    if (( SECONDS > deadline )); then
      echo "Timed out after ${TIMEOUT}s waiting for $name ($url)"
      docker compose ps -a
      return 1
    fi
    sleep 3
  done
  echo "$name is up ($url)"
}

wait_for "API readiness" "$API/api/v1/health/ready"
wait_for "frontend" "$WEB/"

# The one-shot migration container must have finished successfully.
code="$(docker inspect -f '{{.State.ExitCode}}' "$(docker compose ps -a -q migrate)")"
[ "$code" = "0" ] || { echo "migrate exited with $code"; exit 1; }
docker compose ps -a
