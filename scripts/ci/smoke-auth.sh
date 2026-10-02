#!/usr/bin/env bash
# End-to-end auth smoke test against the running Docker stack, entirely
# through the frontend origin (same-origin API proxy + middleware), the way
# a browser uses it. Requires APP_ENV != production (uses the mock outbox).
set -euo pipefail

WEB="${WEB_URL:-http://localhost:3000}"
JAR="$(mktemp)"
EMAIL="smoke-$(date +%s)-$RANDOM@example.com"
PASSWORD="Smoke-Test-Pass-2026"
trap 'rm -f "$JAR"' EXIT

fail() { echo "SMOKE FAIL: $*"; exit 1; }
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

echo "1. anonymous /dashboard redirects to /login"
code=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$WEB/dashboard")
[[ "$code" == 307* && "$code" == *"/login?next=%2Fdashboard"* ]] || fail "guard: $code"

echo "2. register"
curl -fsS -X POST "$WEB/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"اختبار دخان\",\"phone\":\"0770 000 $((1000 + RANDOM % 8999))\"}" \
  | json 'd["user"]["roles"]' | grep -q CUSTOMER || fail "register"

echo "3. verification email in mock outbox"
token=$(curl -fsS "$WEB/api/v1/dev/outbox" | python3 -c "
import json,re,sys
for m in json.load(sys.stdin):
    if m['to']=='$EMAIL' and 'email_verify' in m['tags']:
        print(re.search(r'token=([A-Za-z0-9_-]+)', m['text']).group(1)); break")
[ -n "$token" ] || fail "no verification email"
curl -fsS -X POST "$WEB/api/v1/auth/verify-email" -H 'Content-Type: application/json' \
  -d "{\"token\":\"$token\"}" >/dev/null || fail "verify"

echo "4. login sets httpOnly cookies through the proxy"
headers=$(curl -fsS -D - -o /dev/null -c "$JAR" -X POST "$WEB/api/v1/auth/login" \
  -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
for c in access_token refresh_token csrf_token; do
  grep -qi "^set-cookie: $c=" <<<"$headers" || fail "cookie $c missing"
done
grep -i "^set-cookie: access_token=" <<<"$headers" | grep -qi httponly || fail "access cookie not httpOnly"

echo "5. /auth/me with cookies; email verified"
curl -fsS -b "$JAR" "$WEB/api/v1/auth/me" | json 'd["user"]["email_verified"]' | grep -q True \
  || fail "me"

echo "6. protected page renders for the signed-in user"
curl -fsS -b "$JAR" "$WEB/dashboard" | grep -q "اختبار دخان" || fail "dashboard"

echo "7. CSRF is enforced on cookie-authenticated mutations"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -X POST "$WEB/api/v1/auth/logout-all")
[ "$code" = "403" ] || fail "missing CSRF accepted ($code)"

echo "8. logout with CSRF header revokes the session"
csrf=$(awk '$6=="csrf_token"{print $7}' "$JAR")
cp "$JAR" "$JAR.before"
curl -fsS -b "$JAR" -c "$JAR" -X POST "$WEB/api/v1/auth/logout" -H "X-CSRF-Token: $csrf" >/dev/null
# Replay the pre-logout access cookie: the server-side session must be dead.
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR.before" "$WEB/api/v1/auth/me")
rm -f "$JAR.before"
[ "$code" = "401" ] || fail "session still valid after logout ($code)"

echo "AUTH SMOKE OK"
