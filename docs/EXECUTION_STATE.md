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

## In progress: ONLINE LAUNCH

Blocked on the owner creating the free Supabase project and Render Blueprint
and adding GitHub secrets (SUPABASE_DB_URL, DEMO_ACCOUNT_PASSWORD,
JOBS_TRIGGER_TOKEN). Instructions were sent; see ONLINE-LAUNCH-STATUS.md.

## Next actions (in order)

1. Owner sends the two public URLs → write them to `deploy/live.env`, push.
2. CI → Live site workflow (or dispatch it): fix failures until all jobs green.
3. Tick the checklist in ONLINE-LAUNCH-STATUS.md, record URLs in README.
4. Live deployment report.

## Local tooling notes

Only ruff, black, pytest (without app deps) and prettier run locally; mypy,
the backend test-suite and the frontend build run only in CI. The shell has
no brace expansion — create directories one by one.

## Known failures

None on `main`.
