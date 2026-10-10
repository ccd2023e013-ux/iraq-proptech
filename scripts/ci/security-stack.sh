#!/usr/bin/env bash
# Branch security checks against the CI Docker stack (pre-merge). The live
# security suite (scripts/live/security.sh) runs again against production
# after the merge. Runs after the browser checks: step 4 exhausts a rate limit.
set -euo pipefail
WEB="${WEB_URL:-http://localhost:3000}"
fail() { echo "SECURITY FAIL: $*" >&2; exit 1; }
ok() { echo "  ✓ $*"; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 60 "$@"; }

echo "1. security headers on the market page and API"
page_h=$(curl -sS -D - -o /dev/null "$WEB/market" | tr -d '\r')
for h in "content-security-policy: .*frame-ancestors 'none'" "x-frame-options: deny" "x-content-type-options: nosniff" "referrer-policy:"; do
  grep -qiE "^$h" <<<"$page_h" || fail "market page header missing: $h"
done
api_h=$(curl -sS -D - -o /dev/null "http://localhost:8000/api/v1/market/report?interpret=false" | tr -d '\r')
grep -qiE "^content-security-policy: default-src 'none'" <<<"$api_h" || fail "API CSP"
grep -qi '^x-content-type-options: nosniff' <<<"$api_h" || fail "API nosniff"
ok "CSP, frame, nosniff and referrer headers present"

echo "2. input validation on the market report"
R="$WEB/api/v1/market/report"
[ "$(code "$R?city_id=not-a-uuid")" = 422 ] || fail "invalid uuid accepted"
[ "$(code "$R?city_id=1'%20OR%201=1--")" = 422 ] || fail "injection-shaped id accepted"
[ "$(code "$R?language=fr")" = 422 ] || fail "unknown language accepted"
[ "$(code "$R?include_demo=maybe")" = 422 ] || fail "bad boolean accepted"
[ "$(code "$R?district_id=00000000-0000-0000-0000-000000000000")" = 404 ] || fail "unknown area"
[ "$(code -X POST "$R")" = 405 ] || fail "report accepts POST"
ok "ids, language, booleans and methods validated"

echo "3. no secrets or internal URLs in what the browser downloads"
static=$(docker compose exec -T frontend sh -c 'find / -type d -path "*/.next/static" 2>/dev/null | head -1')
[ -n "$static" ] || fail "no .next/static found in the frontend image"
if docker compose exec -T frontend sh -c "grep -rlE 'JWT_SECRET|DATABASE_URL|POSTGRES_PASSWORD|SUPABASE_SERVICE|sk-[A-Za-z0-9]{20}|BEGIN (RSA )?PRIVATE KEY' '$static'"; then
  fail "secret-like strings in browser bundles"
fi
ok "browser bundles carry no secrets"

echo "4. the market report is rate limited (30/min per IP)"
limited=""
for _ in $(seq 1 45); do
  c=$(code "$R?interpret=false")
  if [ "$c" = 429 ]; then limited=1; break; fi
done
[ -n "$limited" ] || fail "no 429 after 45 rapid market reports"
ok "rate limit enforced"
