#!/usr/bin/env bash
# Install frontend dependencies reproducibly.
#
# This repository is developed in an environment without npm registry access,
# so a dependency added to package.json may arrive before its lockfile entry.
# `npm install --package-lock-only` reconciles the lockfile with package.json
# (a no-op when they already agree), then `npm ci` installs exactly what the
# lockfile pins. The workflow commits a reconciled lockfile back to main.
set -euo pipefail
if [ -f package-lock.json ]; then
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund
  if ! git diff --quiet -- package-lock.json; then
    echo "::notice title=lockfile::package-lock.json was reconciled with package.json"
  fi
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi
