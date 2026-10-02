#!/usr/bin/env bash
# Security checks against the DEPLOYED site. Runs on its own runner because the
# rate-limit check deliberately exhausts the login limit for this runner's IP.
# Usage: WEB_URL=… API_URL=… DEMO_ACCOUNT_PASSWORD=… scripts/live/security.sh
set -euo pipefail

WEB="${WEB_URL:?}"; WEB="${WEB%/}"
API="${API_URL:?}"; API="${API%/}"
PASSWORD="${DEMO_ACCOUNT_PASSWORD:?}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail() { echo "SECURITY FAIL: $*" >&2; exit 1; }
ok() { echo "  ✓ $*"; }
hdr() { curl -sS -D - -o /dev/null --max-time 90 "$@" | tr -d '\r'; }

curl -fsS -o /dev/null --retry 8 --retry-delay 15 --retry-all-errors --max-time 120 "$API/api/v1/health"
curl -fsS -o /dev/null --retry 8 --retry-delay 15 --retry-all-errors --max-time 120 "$WEB/healthz"

echo "1. HTTPS only"
for host in "$WEB" "$API"; do
  [[ "$host" == https://* ]] || fail "$host is not https"
  loc=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 30 "http://${host#https://}/")
  [[ "$loc" == https://* ]] || fail "http not redirected for $host"
done
api_h=$(hdr "$API/api/v1/health")
grep -qi '^strict-transport-security:' <<<"$api_h" || fail "API without HSTS"
ok "https everywhere, http redirects, API sends HSTS"

echo "2. security headers and CSP"
web_h=$(hdr "$WEB/")
for h in "content-security-policy: .*frame-ancestors 'none'" "x-frame-options: deny" "x-content-type-options: nosniff" "referrer-policy:"; do
  grep -qiE "^$h" <<<"$web_h" || fail "web header missing: $h"
done
grep -qiE "^content-security-policy: default-src 'none'" <<<"$api_h" || fail "API CSP"
grep -qi '^x-content-type-options: nosniff' <<<"$api_h" || fail "API nosniff"
! grep -qi '^x-powered-by:' <<<"$web_h" || fail "X-Powered-By exposed"
grep -qi '^strict-transport-security:' <<<"$web_h" && ok "web sends HSTS" \
  || echo "  (note: web HSTS not set by the host; add it at the TLS edge with a custom domain)"
ok "CSP, frame/sniff/referrer protections on web and API"

echo "3. CORS: foreign origins get no access"
cors=$(hdr -H "Origin: https://evil.example" "$API/api/v1/health")
! grep -qi '^access-control-allow-origin:' <<<"$cors" || fail "API allows a foreign origin"
pre=$(hdr -X OPTIONS -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST" "$API/api/v1/auth/login")
! grep -qi '^access-control-allow-origin: https://evil.example' <<<"$pre" || fail "preflight allows a foreign origin"
ok "no CORS grant for foreign origins"

echo "4. session cookies"
login_h=$(curl -sS -D - -o /dev/null -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"demo.customer@example.com\",\"password\":\"$PASSWORD\"}" | tr -d '\r')
grep -i '^set-cookie: access_token=' <<<"$login_h" | grep -qi 'httponly' || fail "access cookie not HttpOnly"
for c in access_token refresh_token csrf_token; do
  line=$(grep -i "^set-cookie: $c=" <<<"$login_h") || fail "cookie $c missing"
  grep -qi 'secure' <<<"$line" || fail "cookie $c not Secure"
  grep -qi 'samesite=lax\|samesite=strict' <<<"$line" || fail "cookie $c without SameSite"
done
ok "HttpOnly + Secure + SameSite session cookies"

echo "5. no internal details, docs or dev tools exposed"
for path in /docs /redoc /openapi.json /api/v1/openapi.json /api/v1/dev/outbox; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$API$path"); [ "$c" = 404 ] || fail "$path answered $c"
done
err=$(curl -s "$API/api/v1/properties/not-a-uuid")
jq -e '.error.code and (.error.request_id | length > 0)' <<<"$err" >/dev/null || fail "error envelope: $err"
! grep -qiE 'traceback|sqlalchemy|psycopg|File "/' <<<"$err" || fail "internal details in errors"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "X-Jobs-Token: wrong-token-wrong-token-wrong-token" "$API/api/v1/internal/jobs/run")
[ "$c" = 404 ] || fail "jobs trigger answers a wrong token with $c"
ok "docs/OpenAPI/dev outbox hidden, error envelope without internals, jobs trigger hidden"

echo "6. path traversal, injection, reflected XSS"
for p in "/api/v1/..%2F..%2Fdocs" "/api/v1/%2e%2e/%2e%2e/openapi.json" "/api/v1/media/..%2f..%2fetc%2fpasswd"; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$WEB$p"); [[ "$c" =~ ^(400|404|422)$ ]] || fail "$p answered $c"
done
c=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/search/properties?q=%27%20OR%201%3D1%20--"); [ "$c" = 200 ] || fail "q injection $c"
c=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/search/properties?city_id=1%20OR%201%3D1"); [ "$c" = 422 ] || fail "id injection $c"
page=$(curl -fsS "$WEB/properties?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E")
! grep -q '<script>alert(1)</script>' <<<"$page" || fail "reflected XSS on the search page"
ok "traversal rejected, injection inert, search input escaped"

echo "7. no secrets in public HTML/JS"
home=$(curl -fsS "$WEB/")
grep -oE '/_next/static/[^"]+\.js' <<<"$home" | sort -u | head -40 > "$TMP/chunks"
cat <<<"$home" > "$TMP/all.txt"
while read -r chunk; do curl -fsS "$WEB$chunk" >> "$TMP/all.txt" || true; done < "$TMP/chunks"
! grep -qiE 'postgres(ql)?://|supabase\.co/storage|S3_SECRET|JWT_SECRET|JOBS_TRIGGER_TOKEN|sk-ant-|service_role' "$TMP/all.txt" \
  || fail "secret-like value in public bundle"
ok "$(wc -l < "$TMP/chunks") bundles scanned, nothing secret"

echo "8. client IP seen by the API = this runner (TRUSTED_PROXY_HOPS correct)"
mine=$(curl -fsS --max-time 20 https://api.ipify.org || true)
probe="ip-probe-$(date +%s)$RANDOM@example.com"
since=$(date -u -d '-10 seconds' +%Y-%m-%dT%H:%M:%SZ)
curl -s -o /dev/null -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$probe\",\"password\":\"wrong-password-123\"}"
rm -f "$TMP/admin.jar"
curl -fsS -c "$TMP/admin.jar" -o /dev/null -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"demo.admin@example.com\",\"password\":\"$PASSWORD\"}"
# Failed-login audit rows deliberately do not store the email: take the newest
# failure since just before the probe (this runner is the only client then).
seen=$(curl -fsS -b "$TMP/admin.jar" "$WEB/api/v1/admin/audit-logs?action=auth.login_failed&since=$since&page_size=5" \
  | jq -r '.items[0].ip_address // empty')
echo "  runner=$mine api-saw=$seen"
echo "::notice title=live client ip summary::runner=$mine api_saw=${seen:-unknown}"
if [ -n "$mine" ] && [ -n "$seen" ]; then
  [ "$seen" = "$mine" ] || fail "API sees $seen instead of the client $mine — adjust TRUSTED_PROXY_HOPS"
  ok "API attributes requests to the real client"
else
  echo "  (could not compare client IP: runner=$mine seen=$seen)"
fi

echo "9. login rate limit (uses this runner's IP budget)"
victim="rate-limit-$(date +%s)@example.com"
got429=0
for i in $(seq 1 30); do
  c=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$victim\",\"password\":\"wrong-password-$i\"}")
  if [ "$c" = 429 ]; then got429=$i; break; fi
done
[ "$got429" -gt 0 ] || fail "no 429 after 30 failed logins"
ok "login throttled after $got429 attempts"

echo "SECURITY CHECKS OK"
echo "::notice title=live security summary::SECURITY CHECKS OK against $WEB"
