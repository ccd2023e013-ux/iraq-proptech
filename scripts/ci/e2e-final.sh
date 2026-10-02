#!/usr/bin/env bash
# Final end-to-end acceptance scenario (16 steps) against the running Docker
# stack, entirely through the public frontend origin (same-origin /api/v1
# proxy, cookie sessions + CSRF), with the mock AI, mock email and demo data.
#
# Setup (S1–S4): an agency owner creates an agency, an administrator verifies
# it, an agent joins by invitation, the agent publishes a Basra listing.
# Then the 16 required steps run in order and each one asserts its outcome.
set -euo pipefail

WEB="${WEB_URL:-http://localhost:3000}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STAMP="$(date +%s)-$RANDOM"
PASSWORD="E2E-Final-Pass-2026"
CUSTOMER="customer-$STAMP@example.com"
OWNER="agency-owner-$STAMP@example.com"
AGENT="agent-$STAMP@example.com"
ADMIN="e2e-admin-$STAMP@example.com"
TITLE="شقة نهائية للاختبار في البصرة $STAMP"

fail() { echo "E2E FAIL: $*"; exit 1; }
jar() { echo "$TMP/$1.jar"; }
csrf() { awk '$6=="csrf_token"{print $7}' "$(jar "$1")"; }
api() { # who METHOD path [json]
  local who="$1" method="$2" path="$3" body="${4:-}"
  local args=(-fsS -b "$(jar "$who")" -X "$method" "$WEB/api/v1$path" -H "X-CSRF-Token: $(csrf "$who")")
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  curl "${args[@]}"
}
status_of() { # who METHOD path -> HTTP code
  curl -s -o /dev/null -w '%{http_code}' -b "$(jar "$1")" -X "$2" "$WEB/api/v1$3" -H "X-CSRF-Token: $(csrf "$1")"
}
register() { # email name
  curl -fsS -X POST "$WEB/api/v1/auth/register" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$PASSWORD\",\"full_name\":\"$2\"}" >/dev/null
}
outbox_token() { # email -> verification token from the dev outbox (mock email)
  curl -fsS "$WEB/api/v1/dev/outbox" | python3 -c "
import json, re, sys
for m in json.load(sys.stdin):
    if m['to'] == '$1':
        hit = re.search(r'token=([A-Za-z0-9_-]+)', m['text'])
        if hit: print(hit.group(1)); break"
}
verify() { # email
  local token; token="$(outbox_token "$1")"
  [ -n "$token" ] || fail "no verification email for $1"
  curl -fsS -X POST "$WEB/api/v1/auth/verify-email" -H 'Content-Type: application/json' \
    -d "{\"token\":\"$token\"}" >/dev/null
}
login() { # who email
  rm -f "$(jar "$1")"
  curl -fsS -c "$(jar "$1")" -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$2\",\"password\":\"$PASSWORD\"}" >/dev/null
}
png() { # path: minimal valid RGB PNG without Pillow
  python3 - "$1" <<'PYEOF'
import struct, sys, zlib
w, h = 64, 48
rows = [b"\x00" + bytes(v for x in range(w) for v in ((x * 3) % 256, (y * 7) % 256, 90)) for y in range(h)]
def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
open(sys.argv[1], "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
PYEOF
}
new_listing() { # who title lat lon -> id (draft with one photo, submitted)
  local id
  id=$(api "$1" POST /properties "{\"title_ar\":\"$2\",\"description_ar\":\"إعلان لاختبار القبول النهائي فقط وليس إعلاناً حقيقياً.\",\"property_type_code\":\"APARTMENT\",\"purpose\":\"SALE\",\"price_amount\":\"150000000\",\"currency\":\"IQD\",\"governorate_id\":\"$GOV\",\"city_id\":\"$CITY\",\"location\":{\"lat\":$3,\"lon\":$4},\"location_privacy\":\"APPROXIMATE\"}" | jq -r .id)
  [ -n "$id" ] && [ "$id" != "null" ] || fail "create listing as $1"
  png "$TMP/photo.png"
  curl -fsS -b "$(jar "$1")" -X POST "$WEB/api/v1/properties/$id/media" -H "X-CSRF-Token: $(csrf "$1")" \
    -F "file=@$TMP/photo.png;type=image/png" -F kind=IMAGE >/dev/null || fail "upload as $1"
  api "$1" POST "/properties/$id/submit" | grep -q '"PENDING_REVIEW"' || fail "submit as $1"
  echo "$id"
}

read -r GOV CITY < <(curl -fsS "$WEB/api/v1/locations/governorates" | python3 -c "
import json, sys, urllib.request
g = [x for x in json.load(sys.stdin) if x['code'] == 'BSR'][0]
c = json.load(urllib.request.urlopen('$WEB/api/v1/locations/cities?governorate_id=' + g['id']))
print(g['id'], [x for x in c if x['slug'] == 'basra'][0]['id'])")

echo "S1. administrator (CLI bootstrap)"
docker compose exec -T -e SUPERADMIN_PASSWORD="$PASSWORD" backend \
  python -m app.cli create-superadmin --email "$ADMIN" --name "E2E Admin" >/dev/null
login admin "$ADMIN"

echo "S2. agency owner registers, verifies, creates an agency; admin verifies the agency"
register "$OWNER" "صاحب مكتب الاختبار"; verify "$OWNER"; login owner "$OWNER"
AGENCY=$(api owner POST /agencies "{\"name_ar\":\"مكتب الاختبار النهائي $STAMP\",\"phone\":\"07709998877\"}" | jq -r .id)
[ -n "$AGENCY" ] && [ "$AGENCY" != "null" ] || fail "create agency"
login owner "$OWNER" # pick up the AGENCY_OWNER role in a fresh session
api admin POST "/agencies/$AGENCY/decision" '{"decision":"VERIFY"}' | grep -q '"VERIFIED"' || fail "verify agency"

echo "S3. agent registers and joins by invitation"
register "$AGENT" "وكيل الاختبار"; verify "$AGENT"
INVITE=$(api owner POST "/agencies/$AGENCY/invitations" "{\"email\":\"$AGENT\"}" | jq -r .id)
login agent "$AGENT"
api agent POST "/agency-invitations/$INVITE/accept" >/dev/null || fail "accept invitation"
login agent "$AGENT"
api agent GET /me/agency | jq -e --arg a "$AGENCY" '.id == $a' >/dev/null \
  || fail "agent not in agency"

echo "S4. agent publishes a listing (approved by the admin)"
ID=$(new_listing agent "$TITLE" 30.515 47.820)
api admin POST "/properties/$ID/moderate" '{"decision":"APPROVE"}' | grep -q '"APPROVED"' || fail "approve listing"
listing=$(api agent GET "/properties/$ID")
[ "$(jq -r .agency_id <<<"$listing")" = "$AGENCY" ] || fail "listing not owned by the agency: $listing"

echo "1. register a customer"
register "$CUSTOMER" "زبون الاختبار النهائي"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CUSTOMER\",\"password\":\"wrong-password-123\"}")
[ "$code" = "401" ] || fail "wrong password accepted ($code)"

echo "2. mock verification (email from the mock outbox)"
verify "$CUSTOMER"

echo "3. login"
login customer "$CUSTOMER"
api customer GET /auth/me | jq -e '.user.email_verified == true' >/dev/null || fail "not verified after login"

echo "4. search (Arabic keyword + Basra + price range)"
q=$(python3 -c "import urllib.parse; print(urllib.parse.quote('شقة نهائية $STAMP'))")
found=$(api customer GET "/search/properties?q=$q&city_id=$CITY&currency=IQD&min_price=100000000&max_price=200000000")
jq -e --arg id "$ID" '[.items[].id] | index($id) != null' <<<"$found" >/dev/null || fail "search: $found"

echo "5. open the property (API + server-rendered page)"
detail=$(api customer GET "/properties/$ID")
[ "$(jq -r .status <<<"$detail")" = "APPROVED" ] || fail "detail status"
[ "$(jq -r .exact_location <<<"$detail")" = "null" ] || fail "exact location leaked to a customer"
curl -fsS -b "$(jar customer)" "$WEB/properties/$ID" | grep -q "$TITLE" || fail "detail page"

echo "6. favorite it"
api customer PUT "/properties/$ID/favorite" >/dev/null
api customer GET /me/favorites/ids | grep -q "$ID" || fail "favorite"

echo "7. send an inquiry"
api customer POST "/properties/$ID/inquiries" \
  '{"name":"زبون الاختبار النهائي","phone":"07701239876","message":"أرغب بمعاينة الشقة هذا الأسبوع."}' >/dev/null

echo "8. the agent receives the lead"
LEAD=$(api agent GET /crm/leads | jq -r --arg p "$ID" '.items[] | select(.property.id == $p) | .id')
[ -n "$LEAD" ] || fail "agent did not receive the lead"
code=$(status_of customer GET "/crm/leads/$LEAD")
[ "$code" = "403" ] || [ "$code" = "404" ] || fail "customer could read the lead ($code)"

echo "9. the agent updates the lead"
api agent POST "/crm/leads/$LEAD/activities" '{"kind":"CALL","body":"اتصال أول مع الزبون"}' >/dev/null
api agent PATCH "/crm/leads/$LEAD" '{"status_code":"QUALIFIED"}' | grep -q '"QUALIFIED"' || fail "lead update"

echo "10. the agency owner views the lead"
owner_view=$(api owner GET "/crm/leads/$LEAD")
[ "$(jq -r .status_code <<<"$owner_view")" = "QUALIFIED" ] || fail "owner view: $owner_view"
api owner GET "/crm/leads/$LEAD/activities" | grep -q "اتصال أول مع الزبون" || fail "owner sees activities"
curl -fsS -b "$(jar owner)" "$WEB/dashboard/crm/leads/$LEAD" | grep -q "اتصال أول مع الزبون" || fail "owner lead page"

echo "11. the admin moderates a property (second listing rejected with a reason)"
ID2=$(new_listing agent "إعلان ثان للمراجعة $STAMP" 30.520 47.830)
api admin POST "/properties/$ID2/moderate" '{"decision":"REJECT","reason_code":"POOR_PHOTOS","reason":"الصور غير واضحة"}' \
  | grep -q '"REJECTED"' || fail "reject listing"
code=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/properties/$ID2")
[ "$code" = "404" ] || fail "rejected listing is public ($code)"

echo "12. MockAI analysis (price analysis + summary, labelled mock)"
price=$(api customer GET "/ai/properties/$ID/price-analysis")
[ "$(jq -r .provider <<<"$price")" = "mock" ] || fail "AI provider: $price"
jq -e '.methodology | length > 0' <<<"$price" >/dev/null || fail "AI methodology missing"
api customer GET "/ai/properties/$ID/summary" | jq -e '.provider == "mock" and (.result | length > 0)' >/dev/null \
  || fail "AI summary"

echo "13. natural-language search"
nl=$(python3 -c "import urllib.parse; print(urllib.parse.quote('شقة للبيع في البصرة'))")
nlres=$(api customer GET "/ai/search?q=$nl&page_size=50")
jq -e '.interpretation.provider == "mock" and .interpretation.result.filters.purpose == "SALE"' <<<"$nlres" >/dev/null \
  || fail "NL interpretation: $(jq -c .interpretation.result <<<"$nlres")"
jq -e --arg id "$ID" '[.items[].id] | index($id) != null' <<<"$nlres" >/dev/null \
  || fail "NL search did not find the listing (total $(jq .total <<<"$nlres"))"

echo "14. map search (viewport around the listing)"
geo=$(curl -fsS "$WEB/api/v1/map/properties?bbox=47.78,30.48,47.86,30.55&zoom=16&exclude_demo=true")
jq -e --arg id "$ID" '[.features[].properties.id] | index($id) != null' <<<"$geo" >/dev/null \
  || fail "map: $(jq -c .meta <<<"$geo")"
jq -e --arg id "$ID2" '[.features[].properties.id] | index($id) == null' <<<"$geo" >/dev/null \
  || fail "rejected listing on the map"

echo "15. notifications generated"
api agent GET "/me/notifications?page_size=50" | jq -e '[.items[].kind] | index("inquiry.received") != null' >/dev/null \
  || fail "agent inquiry notification"
api agent GET "/me/notifications?page_size=50" | jq -e '[.items[].kind] | index("property.rejected") != null or index("listing.rejected") != null' >/dev/null \
  || fail "agent rejection notification ($(api agent GET '/me/notifications?page_size=50' | jq -c '[.items[].kind]'))"
api agent GET /me/notifications/unread-count | jq -e '.unread >= 1' >/dev/null || fail "unread count"

echo "16. audit events recorded"
api admin GET "/admin/audit-logs?action=property.moderation.reject&resource_id=$ID2" | jq -e '.total == 1' >/dev/null \
  || fail "moderation audit event"
api admin GET "/admin/audit-logs?action=property.moderation.approve&resource_id=$ID" | jq -e '.total == 1' >/dev/null \
  || fail "approval audit event"
code=$(status_of customer GET "/admin/audit-logs")
[ "$code" = "403" ] || fail "customer read audit logs ($code)"

echo "E2E FINAL SCENARIO OK (16/16)"
