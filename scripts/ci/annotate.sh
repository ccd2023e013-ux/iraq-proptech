#!/usr/bin/env bash
# Run a CI command; if it fails, publish the tail of its output as a GitHub
# Actions error annotation so failures are readable from the run summary and
# the REST API (annotations), not only from the raw log.
#
# Usage: scripts/ci/annotate.sh "<title>" <command> [args...]
set -uo pipefail

title="$1"
shift

log="$(mktemp)"
"$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}

if [ "$status" -ne 0 ]; then
  # Annotation messages must be URL-escaped (%, CR, LF) and stay well under 64 KB.
  body="$(tail -n 120 "$log" | cut -c1-400)"
  body="${body//'%'/'%25'}"
  body="${body//$'\r'/'%0D'}"
  body="${body//$'\n'/'%0A'}"
  echo "::error title=${title} (exit ${status})::${body}"
fi

rm -f "$log"
exit "$status"
