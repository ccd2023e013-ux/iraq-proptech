#!/usr/bin/env bash
# Live acceptance test against the DEPLOYED site (Render + Supabase), through the
# public web origin exactly like a browser (same-origin /api/v1 proxy, cookie
# sessions + CSRF). Synthetic data only: a throw-away customer
# (e2e-live-<random>@example.com, random per-run password that is never printed)
# and one listing that is created, edited, approved, found, then deleted again.
# On exit — success or failure — the listing is deleted and the throw-away
# customer is suspended by the demo admin. Demo accounts sign in with
# DEMO_ACCOUNT_PASSWORD; the demo admin with its own DEMO_ADMIN_PASSWORD.
#
# Usage: WEB_URL=https://… API_URL=https://… DEMO_ACCOUNT_PASSWORD=… DEMO_ADMIN_PASSWORD=… \
#   scripts/live/acceptance.sh
set -euo pipefail
# Read the whole response: `grep -q` exits at the first match, which makes a
# still-streaming curl fail with exit 23 under pipefail.
grep_all() { grep "$@" >/dev/null; }

WEB="${WEB_URL:?WEB_URL}"; WEB="${WEB%/}"
API="${API_URL:?API_URL}"; API="${API%/}"
PASSWORD="${DEMO_ACCOUNT_PASSWORD:?DEMO_ACCOUNT_PASSWORD}"
ADMIN_PASSWORD="${DEMO_ADMIN_PASSWORD:?DEMO_ADMIN_PASSWORD (the demo admin password)}"
TMP="$(mktemp -d)"
# STAMP only labels synthetic content; credentials come from a CSPRNG.
STAMP="$(date +%s)$RANDOM"
CUSTOMER="e2e-live-$(python3 -c 'import secrets; print(secrets.token_hex(8))')@example.com"
CUSTOMER_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
REGISTERED=""
LISTING=""
# Keep the script's own exit status: cleanup must never turn a pass into a fail
# (or hide a failure).
# shellcheck disable=SC2154  # rc is assigned inside the trap string
trap 'rc=$?; set +e; cleanup; rm -rf "$TMP"; exit "$rc"' EXIT

pass=0
ok() { pass=$((pass + 1)); echo "  ✓ $*"; }
fail() { echo "LIVE FAIL: $*" >&2; exit 1; }
jar() { echo "$TMP/$1.jar"; }
csrf() { awk '$6=="csrf_token"{print $7}' "$(jar "$1")"; }
api() { # who METHOD path [json]  (through the web origin)
  local who="$1" method="$2" path="$3" body="${4:-}"
  local args=(-fsS --max-time 90 -b "$(jar "$who")" -X "$method" "$WEB/api/v1$path" -H "X-CSRF-Token: $(csrf "$who")")
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  curl "${args[@]}"
}
code_of() { # who METHOD path [json] -> HTTP status
  local who="$1" method="$2" path="$3" body="${4:-}"
  local args=(-s -o /dev/null -w '%{http_code}' --max-time 90 -b "$(jar "$who")" -X "$method" "$WEB/api/v1$path" -H "X-CSRF-Token: $(csrf "$who")")
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  curl "${args[@]}"
}
anon() { curl -fsS --max-time 90 "$WEB/api/v1$1"; }
# Credentials go to curl on stdin, never in its arguments (visible to other
# processes on the runner); jq reads them from its environment, not argv.
creds() { E="$1" P="$2" jq -nc '{email: env.E, password: env.P}'; }
try_login() { # who email password -> curl status (no exit)
  rm -f "$(jar "$1")"
  creds "$2" "$3" | curl -fsS --max-time 90 -c "$(jar "$1")" -X POST "$WEB/api/v1/auth/login" \
    -H 'Content-Type: application/json' --data-binary @- >/dev/null
}
login() { try_login "$@" || fail "login $2"; }
urlq() { python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$1"; }
cleanup() {
  if [ -n "$LISTING" ] && [ -f "$(jar owner)" ]; then
    code_of owner DELETE "/properties/$LISTING" >/dev/null || true
  fi
  # The throw-away customer cannot delete itself (no such endpoint), so the demo
  # admin suspends it: suspended accounts cannot sign in and their sessions are
  # revoked. Runs on success and on failure.
  if [ -n "$REGISTERED" ]; then
    [ -f "$(jar admin)" ] || try_login admin demo.admin@example.com "$ADMIN_PASSWORD" || true
    local id
    id=$(api admin GET "/admin/users?q=$(urlq "$CUSTOMER")" 2>/dev/null \
      | jq -r --arg e "$CUSTOMER" '[.items[] | select(.email == $e)][0].id // empty' 2>/dev/null)
    if [ -n "$id" ] \
      && [ "$(code_of admin POST "/admin/users/$id/suspend" '{"reason":"live acceptance throw-away account"}')" = 200 ]; then
      echo "  ✓ cleanup: throw-away customer suspended"
    else
      echo "::warning title=live acceptance cleanup::could not suspend the throw-away customer"
    fi
  fi
}

echo "0. wake the free instances (cold start can take a minute)"
for url in "$API/api/v1/health" "$WEB/healthz"; do
  curl -fsS -o /dev/null --retry 8 --retry-delay 15 --retry-all-errors --max-time 120 "$url" \
    || fail "not reachable: $url"
done
ok "API and web answer"

echo "1. health, readiness, HTTPS"
health=$(curl -fsS "$API/api/v1/health")
jq -e '.status == "ok" and .environment == "production"' <<<"$health" >/dev/null || fail "health $health"
ready=$(curl -fsS "$API/api/v1/health/ready")
jq -e '.database.status == "ok" and .postgis.status == "ok"' <<<"$ready" >/dev/null || fail "ready $ready"
echo "::notice title=live readiness summary::$(jq -c . <<<"$ready") commit=$(jq -r .commit <<<"$health")"
anon /health | jq -e '.status == "ok"' >/dev/null || fail "proxy health"
for host in "$WEB" "$API"; do
  plain="http://${host#https://}"
  loc=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 30 "$plain/")
  [[ "$loc" == https://* ]] || fail "$plain does not redirect to https ($loc)"
done
ok "health/ready ok (database + PostGIS), proxy ok, http→https"

echo "2. Arabic RTL homepage and English"
home=$(curl -fsS "$WEB/")
grep -q 'lang="ar"' <<<"$home" && grep -q 'dir="rtl"' <<<"$home" || fail "home not Arabic RTL"
home_en=$(curl -fsS -b "locale=en" "$WEB/")
grep -q 'lang="en"' <<<"$home_en" && grep -q 'dir="ltr"' <<<"$home_en" || fail "English page"
ok "Arabic RTL default; English via the locale switch"

echo "3. Iraqi DEMO data in seven cities"
read -r -a CITY_IDS < <(anon /locations/governorates | python3 -c "
import json, sys, urllib.request
wanted = {'BSR':'basra','BGD':'baghdad','NJF':'najaf','KRB':'karbala','EBL':'erbil','NIN':'mosul','SUL':'sulaymaniyah'}
out = {}
for g in json.load(sys.stdin):
    if g['code'] in wanted:
        cities = json.load(urllib.request.urlopen('$WEB/api/v1/locations/cities?governorate_id=' + g['id']))
        out[g['code']] = next(c['id'] for c in cities if c['slug'] == wanted[g['code']])
# Basra first: later steps use it as the reference city (IQD prices).
print(' '.join([out.pop('BSR')] + list(out.values())))")
[ "${#CITY_IDS[@]}" = 7 ] || fail "city lookup: ${CITY_IDS[*]}"
total=0
for cid in "${CITY_IDS[@]}"; do
  n=$(anon "/search/properties?city_id=$cid&page_size=1" | jq .total)
  [ "$n" -ge 10 ] || fail "only $n listings in city $cid"
  total=$((total + n))
done
anon "/search/properties?page_size=50" | jq -e '[.items[] | select(.is_demo != true)] | length == 0' >/dev/null \
  || echo "  (note: non-demo listings exist)"
echo "::notice title=live demo data summary::$total public listings across 7 cities"
BASRA="${CITY_IDS[0]}"
ok "$total listings across Basra, Baghdad, Najaf, Karbala, Erbil, Mosul, Sulaymaniyah"

echo "4. search: Arabic, English, natural language, filters"
for q in "بيت للبيع في البصرة|SALE|HOUSE" "شقة للإيجار في بغداد|RENT|APARTMENT" "house for sale in Basra|SALE|HOUSE"; do
  IFS='|' read -r text purpose type <<<"$q"
  r=$(anon "/ai/search?q=$(urlq "$text")&page_size=50")
  jq -e --arg p "$purpose" --arg t "$type" \
    '.total > 0 and ([.items[] | select(.purpose != $p or .property_type_code != $t)] | length == 0)' <<<"$r" >/dev/null \
    || fail "NL search '$text': $(jq -c '{total, f: .interpretation.result.filters}' <<<"$r")"
  ok "\"$text\" → $(jq .total <<<"$r") results ($(jq -r .interpretation.provider <<<"$r"))"
done
kw=$(anon "/search/properties?q=$(urlq "شقة")&city_id=$BASRA&page_size=20")
jq -e '.total > 0' <<<"$kw" >/dev/null || fail "Arabic keyword search"
f=$(anon "/search/properties?city_id=$BASRA&property_types=HOUSE&purpose=SALE&currency=IQD&min_price=100000000&max_price=2000000000&bedrooms_min=3&bathrooms_min=1&min_area=100&max_area=500&page_size=100")
jq -e '.total > 0 and ([.items[] | select(
    .property_type_code != "HOUSE" or .purpose != "SALE" or .currency != "IQD"
    or ((.price_amount | tonumber) < 100000000) or ((.price_amount | tonumber) > 2000000000)
    or (.bedrooms < 3) or (.bathrooms < 1)
    or ((.area_m2 | tonumber) < 100) or ((.area_m2 | tonumber) > 500))] | length == 0)' <<<"$f" >/dev/null \
  || fail "filters: $(jq -c '{total}' <<<"$f")"
ok "filters city/type/purpose/price/bedrooms/bathrooms/area respected ($(jq .total <<<"$f") results)"

echo "5. property details, photo, map, nearby"
PROP=$(jq -r '.items[0].id' <<<"$f")
detail=$(anon "/properties/$PROP")
[ "$(jq -r .exact_location <<<"$detail")" = "null" ] || fail "exact location leaked"
cover=$(jq -r '.media[0].url // empty' <<<"$detail")
[ -n "$cover" ] || fail "demo listing without image"
img=$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' "$WEB$cover")
[ "$img" = "200 image/webp" ] || fail "listing photo $cover answered: $img (photo storage settings on the API?)"
c=$(curl -s -o "$TMP/detail.html" -w '%{http_code}' "$WEB/properties/$PROP")
[ "$c" = 200 ] && grep -q "$(jq -r .reference_code <<<"$detail")" "$TMP/detail.html" || fail "detail page: $c"
geo=$(anon "/map/properties?bbox=47.70,30.45,47.90,30.60&zoom=14")
jq -e '[.features[] | select(.properties.id != null)] | length > 0' <<<"$geo" >/dev/null || fail "map points"
country=$(anon "/map/properties?bbox=38.7,29.0,48.8,37.4&zoom=5")
jq -e '.features | length > 0' <<<"$country" >/dev/null || fail "country map"
c=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/properties/$PROP/nearby"); [ "$c" = 200 ] || fail "nearby places: $c"
lat=$(jq -r .display_location.lat <<<"$detail"); lon=$(jq -r .display_location.lon <<<"$detail")
anon "/search/properties?near_lat=$lat&near_lon=$lon&radius_km=3&sort=distance" | jq -e '.total > 0' >/dev/null \
  || fail "radius search"
ok "details, webp image, map points/clusters ($(jq -r .meta.mode <<<"$country") at country zoom), nearby, radius search"

echo "6. registration, login, logout (new synthetic customer)"
REGISTERED=1 # set before the request: cleanup looks the account up either way
creds "$CUSTOMER" "$CUSTOMER_PASSWORD" | jq -c '. + {full_name: "زبون فحص مباشر"}' \
  | curl -fsS -X POST "$WEB/api/v1/auth/register" -H 'Content-Type: application/json' \
    --data-binary @- >/dev/null \
  || fail "register"
login newcust "$CUSTOMER" "$CUSTOMER_PASSWORD"
api newcust GET /auth/me | jq -e --arg e "$CUSTOMER" '.user.email == $e' >/dev/null || fail "me"
api newcust PUT "/properties/$PROP/favorite" >/dev/null || fail "favorite"
api newcust GET /me/favorites/ids | grep_all "$PROP" || fail "favorite list"
api newcust DELETE "/properties/$PROP/favorite" >/dev/null
code=$(code_of newcust POST "/properties/$PROP/inquiries" '{"name":"زبون","phone":"07701234567","message":"فحص"}')
[ "$code" = "403" ] || fail "unverified inquiry answered $code (expected 403 EMAIL_NOT_VERIFIED)"
api newcust POST /auth/logout >/dev/null
[ "$(code_of newcust GET /auth/me)" = "401" ] || fail "still signed in after logout"
ok "register → login → favorite → logout; unverified accounts cannot send inquiries (email verification)"

echo "7. demo accounts sign in"
login admin demo.admin@example.com "$ADMIN_PASSWORD"
for who in agency agent owner customer; do login "$who" "demo.$who@example.com" "$PASSWORD"; done
AGENCY=$(api agent GET /me/agency | jq -r .id)
[ -n "$AGENCY" ] && [ "$AGENCY" != null ] || fail "demo agent has no agency"
ok "admin, agency owner, agent, owner, customer"

echo "8. inquiry → agent lead → agent update → agency owner view"
APROP=$(anon "/search/properties?agency_id=$AGENCY&page_size=1" | jq -r '.items[0].id')
[ -n "$APROP" ] && [ "$APROP" != null ] || fail "no agency listing"
api customer PUT "/properties/$APROP/favorite" >/dev/null
api customer POST "/properties/$APROP/inquiries" \
  "{\"name\":\"زبون تجريبي\",\"phone\":\"07701239876\",\"message\":\"فحص مباشر $STAMP: هل العقار متاح؟\"}" >/dev/null \
  || fail "inquiry"
LEAD=$(api agent GET "/crm/leads?page_size=100" | jq -r --arg p "$APROP" '[.items[] | select(.property.id == $p)][0].id')
[ -n "$LEAD" ] && [ "$LEAD" != null ] || fail "agent did not receive the lead"
api agent POST "/crm/leads/$LEAD/activities" "{\"kind\":\"NOTE\",\"body\":\"فحص مباشر $STAMP\"}" >/dev/null || fail "activity"
api agent PATCH "/crm/leads/$LEAD" '{"status_code":"CONTACTED"}' | jq -e '.status_code == "CONTACTED"' >/dev/null \
  || fail "lead update"
api agency GET "/crm/leads/$LEAD/activities" | grep_all "$STAMP" || fail "agency owner cannot see the lead"
for page in /dashboard /dashboard/crm "/dashboard/crm/leads/$LEAD"; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' -b "$(jar agent)" "$WEB$page")" = 200 ] || fail "agent page $page"
done
api agent GET "/me/notifications?page_size=50" | jq -e '[.items[].kind] | index("inquiry.received") != null' >/dev/null \
  || fail "agent notification"
ok "lead delivered to the agent, updated, visible to the agency owner; agent notified"

echo "9. listing lifecycle: create → photo → edit → submit → admin approve → public → search → AI"
read -r GOV CITY < <(anon /locations/governorates | python3 -c "
import json, sys, urllib.request
g = [x for x in json.load(sys.stdin) if x['code'] == 'BSR'][0]
c = json.load(urllib.request.urlopen('$WEB/api/v1/locations/cities?governorate_id=' + g['id']))
print(g['id'], [x for x in c if x['slug'] == 'basra'][0]['id'])")
PRICE=$((123000000 + RANDOM * 1000))
LISTING=$(api owner POST /properties "{\"title_ar\":\"بيت فحص مباشر $STAMP (تجريبي)\",\"description_ar\":\"إعلان لفحص الموقع المباشر آلياً وسيُحذف تلقائياً. ليس عرضاً حقيقياً.\",\"property_type_code\":\"HOUSE\",\"purpose\":\"SALE\",\"price_amount\":\"$PRICE\",\"currency\":\"IQD\",\"area_m2\":\"200\",\"bedrooms\":3,\"bathrooms\":2,\"governorate_id\":\"$GOV\",\"city_id\":\"$CITY\",\"location\":{\"lat\":30.512,\"lon\":47.815},\"location_privacy\":\"APPROXIMATE\"}" | jq -r .id)
[ -n "$LISTING" ] && [ "$LISTING" != null ] || fail "create listing"
python3 - "$TMP/p.png" <<'PY'
import struct, sys, zlib
w, h = 64, 48
rows = [b"\x00" + bytes(v for x in range(w) for v in ((x * 4) % 256, (y * 5) % 256, 120)) for y in range(h)]
c = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d) & 0xFFFFFFFF)
open(sys.argv[1], "wb").write(b"\x89PNG\r\n\x1a\n" + c(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + c(b"IDAT", zlib.compress(b"".join(rows))) + c(b"IEND", b""))
PY
curl -fsS -b "$(jar owner)" -X POST "$WEB/api/v1/properties/$LISTING/media" -H "X-CSRF-Token: $(csrf owner)" \
  -F "file=@$TMP/p.png;type=image/png" -F kind=IMAGE | jq -e '.thumbnail_url' >/dev/null || fail "photo upload"
printf '<html><script>alert(1)</script></html>' > "$TMP/x.png"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$(jar owner)" -X POST "$WEB/api/v1/properties/$LISTING/media" \
  -H "X-CSRF-Token: $(csrf owner)" -F "file=@$TMP/x.png;type=image/png" -F kind=IMAGE)
[ "$code" = 415 ] || fail "HTML disguised as PNG accepted ($code)"
api owner PATCH "/properties/$LISTING" '{"bedrooms":4}' | jq -e '.bedrooms == 4' >/dev/null || fail "edit"
api owner POST "/properties/$LISTING/submit" | jq -e '.status == "PENDING_REVIEW"' >/dev/null || fail "submit"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/properties/$LISTING")" = 404 ] || fail "pending listing public"
api admin GET "/admin/moderation/queue?page_size=100" | grep_all "$LISTING" || fail "not in moderation queue"
api admin POST "/properties/$LISTING/moderate" '{"decision":"APPROVE"}' | jq -e '.status == "APPROVED"' >/dev/null \
  || fail "approve"
anon "/properties/$LISTING" | jq -e '.status == "APPROVED"' >/dev/null || fail "approved listing not public"
anon "/search/properties?city_id=$CITY&min_price=$PRICE&max_price=$PRICE&currency=IQD" \
  | jq -e --arg id "$LISTING" '[.items[].id] | index($id) != null' >/dev/null || fail "search does not find it"
summary=$(anon "/ai/properties/$LISTING/summary?language=ar")
jq -e '.provider == "mock" and (.result.summary | length > 0)' <<<"$summary" >/dev/null || fail "AI summary $summary"
anon "/ai/properties/$PROP/price-analysis" | jq -e '.provider == "platform"' >/dev/null || fail "price analysis"
anon "/ai/compare?ids=$PROP,$APROP" | jq -e '.feature == "property.compare"' >/dev/null || fail "AI compare"
api owner POST /ai/text/improve-arabic '{"text":"بيت حلو كلش قريب عالسوق"}' | jq -e '.provider == "mock"' >/dev/null \
  || fail "improve Arabic"
api owner GET "/me/notifications?page_size=50" | jq -e '[.items[].kind] | index("listing.approved") != null' >/dev/null \
  || fail "approval notification"
ok "created, photo uploaded, disguised HTML rejected, edited, approved, public, searchable; AI summary (mock), price analysis + comparison (statistics), Arabic improvement (mock)"

echo "10. admin console and audit"
api admin GET "/admin/users?q=$(urlq "$CUSTOMER")" | jq -e '.total >= 1' >/dev/null || fail "admin users"
api admin GET /admin/stats | jq -e '.' >/dev/null || fail "admin stats"
api admin GET "/admin/reports" | jq -e '.' >/dev/null || fail "admin reports"
api admin GET "/crm/leads?page_size=5" | jq -e '.total >= 1' >/dev/null || fail "admin leads"
api admin GET "/admin/audit-logs?action=property.moderation.approve&resource_id=$LISTING" | jq -e '.total == 1' >/dev/null \
  || fail "audit event"
api admin GET "/analytics/overview?scope=platform" | jq -e '.platform' >/dev/null || fail "analytics"
for page in /admin /admin/moderation /admin/users /admin/reports /admin/audit /admin/analytics; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' -b "$(jar admin)" "$WEB$page")" = 200 ] || fail "admin page $page"
done
ok "users, stats, reports, leads, audit log, analytics, admin pages"

echo "11. authorization: no IDOR, no privilege escalation"
for path in /admin/stats /admin/users /admin/audit-logs "/admin/moderation/queue"; do
  [ "$(code_of customer GET "$path")" = 403 ] || fail "customer reached $path"
done
c=$(code_of customer GET "/crm/leads/$LEAD"); [ "$c" = 403 ] || [ "$c" = 404 ] || fail "customer read lead ($c)"
c=$(code_of customer PATCH "/properties/$LISTING" '{"bedrooms":9}'); [ "$c" = 403 ] || [ "$c" = 404 ] || fail "customer edited listing ($c)"
c=$(code_of customer POST "/properties/$LISTING/moderate" '{"decision":"SUSPEND","reason":"x"}'); [ "$c" = 403 ] || fail "customer moderated ($c)"
CUST_ID=$(api customer GET /auth/me | jq -r .user.id)
c=$(code_of customer PUT "/admin/users/$CUST_ID/roles/ADMIN"); [ "$c" = 403 ] || fail "self-promotion ($c)"
c=$(code_of agent PUT "/admin/users/$CUST_ID/roles/SUPER_ADMIN"); [ "$c" = 403 ] || fail "agent granted roles ($c)"
c=$(code_of admin PUT "/admin/users/$CUST_ID/roles/SUPER_ADMIN"); [ "$c" = 403 ] || fail "admin granted SUPER_ADMIN ($c)"
c=$(code_of owner GET "/crm/leads/$LEAD"); [ "$c" = 403 ] || [ "$c" = 404 ] || fail "other user read lead ($c)"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/auth/me")" = 401 ] || fail "anonymous /auth/me"
c=$(curl -s -o /dev/null -w '%{http_code}' -b "$(jar customer)" -X POST "$WEB/api/v1/properties/$PROP/inquiries" \
  -H 'Content-Type: application/json' -d '{"name":"x","phone":"07701234567","message":"no csrf"}')
[ "$c" = 403 ] || fail "cookie request without CSRF token accepted ($c)"
ok "customer/agent/admin boundaries hold; CSRF enforced"

echo "12. delete the test listing"
api owner DELETE "/properties/$LISTING" >/dev/null || fail "delete"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/properties/$LISTING")" = 404 ] || fail "deleted listing visible"
LISTING=""
ok "deleted and no longer public"

echo "LIVE ACCEPTANCE OK ($pass checks)"
echo "::notice title=live acceptance summary::LIVE ACCEPTANCE OK — $pass checks passed against $WEB"
