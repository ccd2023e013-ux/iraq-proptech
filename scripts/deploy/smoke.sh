#!/usr/bin/env bash
# Deployment smoke test — run after every deploy (Render/Supabase, the production
# PC, or CI's production rehearsal). Read-only: creates no data.
# Usage: scripts/deploy/smoke.sh https://web.example [https://api.example]
#   With only the web URL, API checks go through the frontend's /api proxy.
set -euo pipefail
WEB="${1:?usage: smoke.sh <web-url> [api-url]}"; WEB="${WEB%/}"
API="${2:-$WEB}"; API="${API%/}"
fail() { echo "SMOKE FAIL: $*"; exit 1; }
get() { curl -sS --max-time 60 --retry 3 --retry-delay 10 --retry-all-errors "$@"; }

echo "1. API liveness (wakes sleeping free instances)"
health=$(get -f "$API/api/v1/health") || fail "health"
env=$(jq -r .environment <<<"$health"); echo "   environment=$env version=$(jq -r .version <<<"$health")"

echo "2. readiness: database + PostGIS"
ready=$(get "$API/api/v1/health/ready")
[ "$(jq -r .database.status <<<"$ready")" = "ok" ] || fail "database: $ready"
[ "$(jq -r .postgis.status <<<"$ready")" = "ok" ] || fail "postgis: $ready"
echo "   redis=$(jq -r .redis.status <<<"$ready") (optional on worker-less hosts)"

echo "3. reference data present (migrations ran)"
n=$(get -f "$API/api/v1/locations/governorates" | jq length)
[ "$n" = "19" ] || fail "expected 19 governorates, got $n"

echo "4. frontend renders Arabic RTL and proxies the API"
page=$(get -f "$WEB/") || fail "frontend"
grep -q 'dir="rtl"' <<<"$page" || fail "home page is not RTL"
get -f "$WEB/api/v1/health" | jq -e '.status == "ok"' >/dev/null || fail "frontend proxy"
headers=$(get -sSI "$WEB/")
grep -qi '^x-frame-options: DENY' <<<"$headers" || fail "frontend X-Frame-Options"
grep -qi "^content-security-policy: .*frame-ancestors 'none'" <<<"$headers" || fail "frontend Content-Security-Policy"
grep -qi '^x-content-type-options: nosniff' <<<"$headers" || fail "frontend nosniff"

echo "5. search and map endpoints answer"
get -f "$API/api/v1/search/properties?page_size=1" | jq -e 'has("total")' >/dev/null || fail "search"
get -f "$API/api/v1/map/properties?zoom=6" | jq -e '.type == "FeatureCollection"' >/dev/null || fail "map"

echo "6. maintenance trigger is hidden without its token"
code=$(get -o /dev/null -w '%{http_code}' -X POST "$API/api/v1/internal/jobs/run")
[ "$code" = "404" ] || fail "jobs trigger answered $code without a token"

if [ "$env" = "production" ]; then
  echo "7. production hardening"
  for path in /docs /api/v1/openapi.json /api/v1/dev/outbox; do
    code=$(get -o /dev/null -w '%{http_code}' "$API$path")
    [ "$code" = "404" ] || fail "$path is exposed ($code)"
  done
  get -D - -o /dev/null "$API/api/v1/health" | grep -qi '^strict-transport-security:' || fail "API HSTS header"
fi
echo "DEPLOY SMOKE OK ($env)"
