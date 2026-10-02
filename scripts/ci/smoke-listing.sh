#!/usr/bin/env bash
# Listing end-to-end smoke test against the running Docker stack, through the
# frontend origin: owner creates a listing, uploads a photo (multipart through
# the Next.js proxy), submits; an administrator approves; an anonymous visitor
# sees it with an approximate location and can load the thumbnail.
set -euo pipefail

WEB="${WEB_URL:-http://localhost:3000}"
OWNER_JAR="$(mktemp)"; ADMIN_JAR="$(mktemp)"; IMG="$(mktemp --suffix=.png)"
trap 'rm -f "$OWNER_JAR" "$ADMIN_JAR" "$IMG"' EXIT
STAMP="$(date +%s)-$RANDOM"
OWNER="owner-$STAMP@example.com"
ADMIN="admin-$STAMP@example.com"
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

echo "LISTING SMOKE OK"
