#!/usr/bin/env bash
# Run a CI command; if it fails, publish the tail of its output as GitHub
# Actions error annotations so failures are readable from the run summary and
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
  # GitHub truncates long annotation messages, so publish the last lines of
  # output in ordered chunks (max 9 per step), each URL-escaped.
  chunks="$(mktemp -d)"
  tail -n 300 "$log" | sed 's/\x1b\[[0-9;]*m//g' | cut -c1-300 | split -C 3500 -d -a 2 - "$chunks/part-"
  files=("$chunks"/part-*)
  start=$(( ${#files[@]} > 9 ? ${#files[@]} - 9 : 0 ))
  for (( i = start; i < ${#files[@]}; i++ )); do
    body="$(cat "${files[$i]}")"
    body="${body//'%'/'%25'}"
    body="${body//$'\r'/'%0D'}"
    body="${body//$'\n'/'%0A'}"
    echo "::error title=${title} (exit ${status}) [part $(( i - start + 1 ))]::${body}"
  done
  rm -rf "$chunks"
fi

rm -f "$log"
exit "$status"
