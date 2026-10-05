#!/usr/bin/env bash
# GIS smoke test against the running Docker stack (through the frontend proxy):
# seed labelled DEMO data, query map GeoJSON for a Basra viewport, resolve a
# point to its (demo) district, and render the map page server-side.
set -euo pipefail
# Read the whole response: `grep -q` exits at the first match, which makes a
# still-streaming curl fail with exit 23 under pipefail.
grep_all() { grep "$@" >/dev/null; }

WEB="${WEB_URL:-http://localhost:3000}"
fail() { echo "SMOKE FAIL: $*"; exit 1; }

echo "1. seed DEMO districts and listings (idempotent)"
docker compose exec -T backend python -m app.cli seed-demo --listings 30
docker compose exec -T backend python -m app.cli seed-demo --listings 30 | grep_all "'listings_created': 0" \
  || fail "seed is not idempotent"

echo "2. map GeoJSON for a Basra viewport"
geo=$(curl -fsS "$WEB/api/v1/map/properties?bbox=47.70,30.45,47.90,30.60&zoom=13")
[ "$(jq -r .type <<<"$geo")" = "FeatureCollection" ] || fail "not GeoJSON"
demo=$(jq '[.features[] | select(.properties.is_demo == true)] | length' <<<"$geo")
[ "$demo" -ge 30 ] || fail "expected >= 30 demo points, got $demo"
jq -e '[.features[] | .geometry.coordinates[0]] | all(. >= 47.70 and . <= 47.90)' <<<"$geo" >/dev/null \
  || fail "points outside the viewport"
jq -e '[.features[].properties | has("location")] | any | not' <<<"$geo" >/dev/null || fail "exact location field leaked"

echo "3. demo listings can be excluded"
real=$(curl -fsS "$WEB/api/v1/map/properties?bbox=47.70,30.45,47.90,30.60&exclude_demo=true")
jq -e '[.features[].properties.is_demo] | all(. == false)' <<<"$real" >/dev/null || fail "exclude_demo"

echo "4. clusters at country zoom when dense are well-formed"
curl -fsS "$WEB/api/v1/map/properties?zoom=5" | jq -e '.meta.mode == "points" or .meta.mode == "clusters"' >/dev/null \
  || fail "map meta"

echo "5. point resolves to the DEMO Al-Ashar district boundary"
res=$(curl -fsS "$WEB/api/v1/locations/resolve?lat=30.512&lon=47.816")
[ "$(jq -r .method <<<"$res")" = "boundary" ] || fail "resolve: $res"
[ "$(jq -r .district.name_en <<<"$res")" = "Al-Ashar" ] || fail "resolve district: $res"
city=$(curl -fsS "$WEB/api/v1/locations/governorates" | jq -r '.[] | select(.code=="BSR") | .id')
bounds=$(curl -fsS "$WEB/api/v1/locations/cities?governorate_id=$city" | jq -r '.[] | select(.slug=="basra") | .id')
curl -fsS "$WEB/api/v1/locations/boundaries?level=districts&parent_id=$bounds" \
  | jq -e '[.features[].properties.geometry_source] | all(startswith("DEMO"))' >/dev/null || fail "boundary labels"

echo "6. map page renders (RTL) with the map shell"
page=$(curl -fsS "$WEB/map?governorate_id=$city")
grep -q 'dir="rtl"' <<<"$page" || fail "map page not RTL"
grep -q 'البحث على الخريطة' <<<"$page" || fail "map page title"
grep -q 'map-canvas' <<<"$page" || fail "map container"

echo "7. nearby POIs, nearby listings and comparison for demo listings"
ids=$(jq -r '[.features[] | select(.properties.is_demo == true) | .properties.id] | .[0:2] | join(",")' <<<"$geo")
first=${ids%%,*}
curl -fsS "$WEB/api/v1/properties/$first/nearby?radius_m=2000" | jq -e '.available and .total > 0' >/dev/null \
  || fail "nearby POIs"
curl -fsS "$WEB/api/v1/properties/$first/nearby-properties" | jq -e '.items | length > 0' >/dev/null \
  || fail "nearby properties"
curl -fsS "$WEB/api/v1/properties/compare?ids=$ids" | jq -e '.items | length == 2' >/dev/null || fail "compare API"
curl -fsS "$WEB/compare?ids=$ids" | grep_all 'مقارنة العقارات' || fail "compare page"
curl -fsS "$WEB/properties/$first" | grep_all 'ما حول العقار' || fail "nearby section on detail page"

echo "8. AI (mock provider): estimate, NL search, smart search page"
curl -fsS "$WEB/api/v1/ai/properties/$first/price-analysis" \
  | jq -e '.kind == "estimate" and .provider == "platform" and (.limitations | length) > 0' >/dev/null \
  || fail "price analysis"
q=$(python3 -c "import urllib.parse;print(urllib.parse.quote('بيت للبيع في البصرة'))")
curl -fsS "$WEB/api/v1/ai/search?q=$q" \
  | jq -e '.interpretation.result.filters.purpose == "SALE" and (.interpretation.result.filters.city_id | length) > 0' >/dev/null \
  || fail "NL search"
curl -fsS "$WEB/search/smart?q=$q" | grep_all 'فهمنا من طلبك' || fail "smart search page"

echo "MAP SMOKE OK"
