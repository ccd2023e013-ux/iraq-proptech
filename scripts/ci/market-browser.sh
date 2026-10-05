#!/usr/bin/env bash
# Stage 8 pre-merge check: the market page in a real browser against the CI
# Docker stack (Render only deploys main, so a branch cannot be checked live).
# National DEMO data gives Basra and Baghdad; one snapshot is recorded so the
# "supply over time" gap is exercised honestly (a single day is not a trend).
set -euo pipefail

WEB="${WEB_URL:-http://localhost:3000}"

echo "1. national DEMO dataset (7 cities, no images) and today's snapshot"
docker compose exec -T backend python -m app.cli seed-demo-iraq --per-city 18 --no-images
docker compose exec -T backend python -m app.cli run-jobs market_snapshot

echo "2. Playwright + Chromium"
python -m pip install --quiet playwright pillow
python -m playwright install --with-deps chromium >/dev/null

echo "3. market page: 1920/1440/390, dark/light, AR/EN, Basra/Baghdad, demo exclusion"
WEB_URL="$WEB" BROWSER_ONLY=market python scripts/live/browser_check.py
