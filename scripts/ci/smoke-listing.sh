#!/usr/bin/env bash
# Listing end-to-end smoke test against the running Docker stack, through the
# frontend origin: owner creates a listing, uploads a photo (multipart through
# the Next.js proxy), submits; an administrator approves; an anonymous visitor
# sees it with an approximate location and can load the thumbnail; search,
# favorites and the public pages find it.
set -euo pipefail

WEB="${WEB_URL:-http://localhost:3000}"
OWNER_JAR="$(mktemp)"; ADMIN_JAR="$(mktemp)"; BUYER_JAR="$(mktemp)"; IMG="$(mktemp --suffix=.png)"
trap 'rm -f "$OWNER_JAR" "$ADMIN_JAR" "$BUYER_JAR" "$IMG"' EXIT
STAMP="$(date +%s)-$RANDOM"
OWNER="owner-$STAMP@example.com"
ADMIN="admin-$STAMP@example.com"
BUYER="buyer-$STAMP@example.com"
PASSWORD="Smoke-Test-Pass-2026"

fail() { echo "SMOKE FAIL: $*"; exit 1; }
py() { python3 -c "$1"; }
csrf() { awk '$6=="csrf_token"{print $7}' "$1"; }

login() { # jar email
  curl -fsS -c "$1" -X POST "$WEB/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$2\",\"password\":\"$PASSWORD\"}" >/dev/null
}

echo "1. register + verify a property owner"
curl -fsS -X POST "$WEB/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$OWNER\",\"password\":\"$PASSWORD\",\"full_name\":\"مالك تجريبي\",\"account_type\":\"PROPERTY_OWNER\"}" >/dev/null
token=$(curl -fsS "$WEB/api/v1/dev/outbox" | py "
import json,re,sys
for m in json.load(sys.stdin):
    if m['to']=='$OWNER': print(re.search(r'token=([A-Za-z0-9_-]+)', m['text']).group(1)); break")
curl -fsS -X POST "$WEB/api/v1/auth/verify-email" -H 'Content-Type: application/json' -d "{\"token\":\"$token\"}" >/dev/null
login "$OWNER_JAR" "$OWNER"

echo "2. reference data and a Basra location"
read -r GOV CITY < <(curl -fsS "$WEB/api/v1/locations/governorates" | py "
import json,sys,urllib.request
g=[x for x in json.load(sys.stdin) if x['code']=='BSR'][0]
c=json.load(urllib.request.urlopen('$WEB/api/v1/locations/cities?governorate_id='+g['id']))
print(g['id'], [x for x in c if x['slug']=='basra'][0]['id'])")

echo "3. create a draft listing"
listing=$(curl -fsS -b "$OWNER_JAR" -X POST "$WEB/api/v1/properties" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" \
  -d "{\"title_ar\":\"بيت تجريبي في العشار\",\"description_ar\":\"وصف تجريبي لاختبار النظام فقط وليس إعلاناً حقيقياً.\",\"property_type_code\":\"HOUSE\",\"purpose\":\"SALE\",\"price_amount\":\"200000000\",\"currency\":\"IQD\",\"governorate_id\":\"$GOV\",\"city_id\":\"$CITY\",\"location\":{\"lat\":30.509,\"lon\":47.816},\"location_privacy\":\"APPROXIMATE\"}")
ID=$(jq -r .id <<<"$listing")
[ -n "$ID" ] || fail "create"

echo "4. upload a photo through the proxy (multipart)"
python3 - "$IMG" <<'PYEOF'
# Minimal valid RGB PNG (no Pillow needed on the CI host).
import struct, sys, zlib
w, h = 64, 48
rows = [b"\x00" + bytes(v for x in range(w) for v in ((x * 4) % 256, (y * 5) % 256, 120)) for y in range(h)]
def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
open(sys.argv[1], "wb").write(png)
PYEOF
media=$(curl -fsS -b "$OWNER_JAR" -X POST "$WEB/api/v1/properties/$ID/media" \
  -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" -F "file=@$IMG;type=image/png" -F kind=IMAGE)
THUMB=$(jq -r .thumbnail_url <<<"$media")
[[ "$THUMB" == /api/v1/media/* ]] || fail "upload: $media"

echo "5. submit for review"
curl -fsS -b "$OWNER_JAR" -X POST "$WEB/api/v1/properties/$ID/submit" \
  -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" | grep -q '"PENDING_REVIEW"' || fail "submit"
code=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/v1/properties/$ID")
[ "$code" = "404" ] || fail "pending listing visible publicly ($code)"

echo "6. administrator (created with the CLI) approves"
docker compose exec -T -e SUPERADMIN_PASSWORD="$PASSWORD" backend \
  python -m app.cli create-superadmin --email "$ADMIN" --name "Smoke Admin" >/dev/null
login "$ADMIN_JAR" "$ADMIN"
curl -fsS -b "$ADMIN_JAR" -X POST "$WEB/api/v1/properties/$ID/moderate" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$ADMIN_JAR")" \
  -d '{"decision":"APPROVE"}' | grep -q '"APPROVED"' || fail "approve"

echo "7. anonymous visitor: approximate location only, photo loads"
public=$(curl -fsS "$WEB/api/v1/properties/$ID")
[ "$(jq -r .exact_location <<<"$public")" = "null" ] || fail "exact location leaked"
[ "$(jq -r .status <<<"$public")" = "APPROVED" ] || fail "not approved"
[ "$(jq -r '.display_location.lat' <<<"$public")" != "30.509" ] || fail "location not coarsened"
[ "$(jq '.media | length' <<<"$public")" = "1" ] || fail "media missing"
ctype=$(curl -fsS -o /dev/null -w '%{content_type}' "$WEB$THUMB")
[ "$ctype" = "image/webp" ] || fail "thumbnail content type $ctype"

echo "8. listing page renders server-side for the owner"
curl -fsS -b "$OWNER_JAR" "$WEB/dashboard/properties" | grep -q "بيت تجريبي في العشار" || fail "dashboard list"

echo "9. search: Arabic keyword with spelling variants + price filter finds it"
# 'تجريبى' (alef maqsura) must match 'تجريبي' via normalize_ar.
q=$(py "import urllib.parse;print(urllib.parse.quote('بيت تجريبى'))")
found=$(curl -fsS "$WEB/api/v1/search/properties?q=$q&currency=IQD&min_price=100000000&max_price=300000000&city_id=$CITY")
jq -e --arg id "$ID" '[.items[].id] | index($id) != null' <<<"$found" >/dev/null || fail "keyword search: $found"
none=$(curl -fsS "$WEB/api/v1/search/properties?q=$q&currency=USD&min_price=1")
jq -e --arg id "$ID" '[.items[].id] | index($id) == null' <<<"$none" >/dev/null || fail "currency filter converted prices"

echo "10. favorite it and see it in /me/favorites"
curl -fsS -b "$OWNER_JAR" -X PUT "$WEB/api/v1/properties/$ID/favorite" -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" >/dev/null
curl -fsS -b "$OWNER_JAR" "$WEB/api/v1/me/favorites/ids" | grep -q "$ID" || fail "favorite"

echo "11. public search and detail pages render server-side"
curl -fsS "$WEB/properties?q=$q" | grep -q "بيت تجريبي في العشار" || fail "search page"
curl -fsS "$WEB/properties/$ID" | grep -q "بيت تجريبي في العشار" || fail "detail page"
curl -fsS -b "$OWNER_JAR" "$WEB/favorites" | grep -q "بيت تجريبي في العشار" || fail "favorites page"

echo "12. a customer registers, verifies and sends an inquiry"
curl -fsS -X POST "$WEB/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$BUYER\",\"password\":\"$PASSWORD\",\"full_name\":\"زبون تجريبي\"}" >/dev/null
btoken=$(curl -fsS "$WEB/api/v1/dev/outbox" | py "
import json,re,sys
for m in json.load(sys.stdin):
    if m['to']=='$BUYER': print(re.search(r'token=([A-Za-z0-9_-]+)', m['text']).group(1)); break")
curl -fsS -X POST "$WEB/api/v1/auth/verify-email" -H 'Content-Type: application/json' -d "{\"token\":\"$btoken\"}" >/dev/null
login "$BUYER_JAR" "$BUYER"
curl -fsS -b "$BUYER_JAR" -X POST "$WEB/api/v1/properties/$ID/inquiries" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$BUYER_JAR")" \
  -d '{"name":"زبون تجريبي","phone":"07701234567","message":"هل العقار متاح للمعاينة؟"}' >/dev/null

echo "13. the owner receives the lead, works it, and replies"
leads=$(curl -fsS -b "$OWNER_JAR" "$WEB/api/v1/crm/leads")
LEAD=$(jq -r --arg p "$ID" '.items[] | select(.property.id == $p) | .id' <<<"$leads")
[ -n "$LEAD" ] || fail "lead not received: $leads"
curl -fsS -b "$OWNER_JAR" -X POST "$WEB/api/v1/crm/leads/$LEAD/activities" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" \
  -d '{"kind":"CALL","body":"تم الاتصال"}' >/dev/null
curl -fsS -b "$OWNER_JAR" -X PATCH "$WEB/api/v1/crm/leads/$LEAD" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" \
  -d '{"status_code":"QUALIFIED"}' | grep -q '"QUALIFIED"' || fail "lead update"
CONV=$(curl -fsS -b "$OWNER_JAR" "$WEB/api/v1/me/conversations" | jq -r '.[0].id')
curl -fsS -b "$OWNER_JAR" -X POST "$WEB/api/v1/conversations/$CONV/messages" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$OWNER_JAR")" \
  -d '{"body":"نعم، متاح يوم السبت"}' >/dev/null

echo "14. the customer sees the reply; the CRM pages render for the owner"
curl -fsS -b "$BUYER_JAR" "$WEB/api/v1/conversations/$CONV/messages" | grep -q "متاح يوم السبت" || fail "reply"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$BUYER_JAR" "$WEB/api/v1/crm/leads/$LEAD")
[ "$code" = "403" ] || fail "customer could read the CRM ($code)"
curl -fsS -b "$OWNER_JAR" "$WEB/dashboard/crm" | grep -q "زبون تجريبي" || fail "CRM page"
curl -fsS -b "$OWNER_JAR" "$WEB/dashboard/crm/leads/$LEAD" | grep -q "تم الاتصال" || fail "lead page"
curl -fsS -b "$BUYER_JAR" "$WEB/messages/$CONV" | grep -q "متاح يوم السبت" || fail "thread page"

echo "15. the customer reports the listing; the admin sees and dismisses it"
REPORT=$(curl -fsS -b "$BUYER_JAR" -X POST "$WEB/api/v1/reports" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$BUYER_JAR")" \
  -d "{\"target_type\":\"PROPERTY\",\"target_id\":\"$ID\",\"reason\":\"INCORRECT\",\"details\":\"السعر غير صحيح\"}" | jq -r .id)
[ -n "$REPORT" ] && [ "$REPORT" != "null" ] || fail "report"
curl -fsS -b "$ADMIN_JAR" "$WEB/admin/reports" | grep -q "السعر غير صحيح" || fail "admin reports page"
curl -fsS -b "$ADMIN_JAR" -X POST "$WEB/api/v1/admin/reports/$REPORT/resolve" \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(csrf "$ADMIN_JAR")" \
  -d '{"outcome":"DISMISSED","note":"تم التحقق من السعر"}' | grep -q '"DISMISSED"' || fail "resolve report"

echo "16. admin pages render (overview, moderation, system, audit)"
for page in /admin /admin/moderation /admin/system /admin/audit /admin/settings; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -b "$ADMIN_JAR" "$WEB$page")
  [ "$code" = "200" ] || fail "admin page $page ($code)"
done
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$BUYER_JAR" "$WEB/api/v1/admin/stats")
[ "$code" = "403" ] || fail "customer reached admin stats ($code)"
curl -fsS -b "$ADMIN_JAR" "$WEB/api/v1/admin/audit-logs?action=report.dismissed" | jq -e '.total >= 1' >/dev/null \
  || fail "audit record for the dismissal"

echo "LISTING SMOKE OK"
