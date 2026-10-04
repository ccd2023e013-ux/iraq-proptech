#!/usr/bin/env bash
# Diagnostic probe of the deployed services: status codes, headers, bodies of
# the key endpoints, printed as GitHub notices (readable via the REST API).
# Usage: WEB_URL=… API_URL=… scripts/live/probe.sh
set -uo pipefail
WEB="${WEB_URL%/}"; API="${API_URL%/}"
note() { local t="$1"; shift; local b="$*"; b="${b//'%'/'%25'}"; b="${b//$'\n'/'%0A'}"; echo "::notice title=probe $t::$b"; }
probe() { # title url [curl args]
  local t="$1" u="$2"; shift 2
  local out
  out=$(curl -sS -m 150 -D - -o /tmp/body "$@" "$u" 2>&1 | tr -d '\r' | head -25)
  note "$t" "$u"$'\n'"$out"$'\n'"--- body:"$'\n'"$(head -c 1200 /tmp/body 2>/dev/null)"
}
probe api-health "$API/api/v1/health"
probe api-ready "$API/api/v1/health/ready"
probe web-root "$WEB/"
sleep 20
probe web-root-again "$WEB/"
probe web-healthz "$WEB/healthz"
probe web-proxy-health "$WEB/api/v1/health"
probe web-status "$WEB/status"
exit 0
