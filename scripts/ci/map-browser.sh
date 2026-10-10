#!/usr/bin/env bash
# Pre-merge map checks in a real browser against the CI Docker stack.
#
# The real-browser map checks used to run only against production (Live site).
# Since the MapLibre 6 upgrade they also gate every pull request:
#   - scripts/live/browser_check.py BROWSER_ONLY=map — price bubbles, places
#     layer, draw-area search, "near me", Future Iraq layer (unchanged checks);
#   - scripts/ci/maplibre_check.py — 8 states (AR/EN x light/dark x desktop/
#     phone): canvas, bubbles, direction, attribution content, no overflow,
#     no CSP/worker/page errors, theme switch (setStyle) redraws overlays.
# Runs after smoke-map.sh, which seeds the Basra DEMO listings and places.
set -euo pipefail

WEB="${WEB_URL:-http://localhost:3000}"

echo "1. curated Future Iraq dataset (bundled, source-cited) for the map layer"
docker compose exec -T backend python -m app.cli import-development --dataset basra

echo "2. Playwright + Chromium"
python -m pip install --quiet playwright pillow
python -m playwright install --with-deps chromium >/dev/null

# Both checks always run (the first one prints console/network diagnostics);
# the step fails at the end if either failed.
status=0
echo "3. MapLibre: 8 states, attribution, CSP/worker, theme switch"
WEB_URL="$WEB" python scripts/ci/maplibre_check.py || status=1

echo "4. map checks (bubbles, places, drawing, near me, Future Iraq)"
WEB_URL="$WEB" BROWSER_ONLY=map python scripts/live/browser_check.py || status=1

exit "$status"
