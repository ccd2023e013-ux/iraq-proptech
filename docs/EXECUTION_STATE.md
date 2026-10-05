# Execution state

Read this first when resuming work in a new session.

- **Repository**: `ccd2023e013-ux/iraq-proptech`, branch `main`
- **Verification authority**: GitHub Actions (`.github/workflows/ci.yml`).
  Job logs cannot be downloaded from the development environment; failures
  are republished as check-run annotations by `scripts/ci/annotate.sh`
  (`gh api repos/<repo>/check-runs/<id>/annotations`).
- **Last green commit**: `195449e` — CI run [37065196155](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37065196155).

## Completed

All phases (1–12), final audit, 16-step E2E. Online-launch preparation
(national DEMO dataset, demo accounts from DEMO_ACCOUNT_PASSWORD, labelled AI,
Live site workflow, docs/ONLINE-LAUNCH-STATUS.md) — CI green at `f5e2c47`.

## Online launch: DONE

Live at https://iraq-proptech-web.onrender.com (API
https://iraq-proptech-api.onrender.com). Verified by the Live site workflow
run 37247712779 on `4ae902d` (all jobs green). Details and the issues fixed
during launch: ONLINE-LAUNCH-STATUS.md.

## Next actions

Owner options: free SMTP sender (public sign-ups), custom domain (+ web HSTS),
production PC migration (MIGRATE-TO-LOCAL-PC.md).

## Local tooling notes

Only ruff, black, pytest (without app deps) and prettier run locally; mypy,
the backend test-suite and the frontend build run only in CI. The shell has
no brace expansion — create directories one by one.

## Known failures

None on `main`.
