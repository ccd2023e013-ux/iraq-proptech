# Execution state

Read this first when resuming work in a new session.

- **Repository**: `ccd2023e013-ux/iraq-proptech`, branch `main`
- **Verification authority**: GitHub Actions (`.github/workflows/ci.yml`).
  Job logs cannot be downloaded from the development environment; failures
  are republished as check-run annotations by `scripts/ci/annotate.sh`
  (`gh api repos/<repo>/check-runs/<id>/annotations`).
- **Last green commit**: `195449e` — CI run [37065196155](https://github.com/ccd2023e013-ux/iraq-proptech/actions/runs/37065196155).

## Completed

All phases (1–12), the final security audit and the 16-step E2E scenario —
see [PHASE-STATUS.md](PHASE-STATUS.md). The build directive is finished.

## Next actions

None required by the directive. Owner actions to go live are listed in
[RENDER.md](RENDER.md), [SUPABASE.md](SUPABASE.md) and
[MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md); future work in
[ROADMAP.md](ROADMAP.md).

## Local tooling notes

Only ruff, black, pytest (without app deps) and prettier run locally; mypy,
the backend test-suite and the frontend build run only in CI. The shell has
no brace expansion — create directories one by one.

## Known failures

None on `main`.
