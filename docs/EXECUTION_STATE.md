# Execution state

Read this first when resuming work in a new session.

- **Repository**: `ccd2023e013-ux/iraq-proptech`, branch `main`
- **Verification authority**: GitHub Actions (`.github/workflows/ci.yml`).
  Job logs cannot be downloaded from the development environment; failures
  are republished as check-run annotations by `scripts/ci/annotate.sh`
  (`gh api repos/<repo>/check-runs/<id>/annotations`).
- **Last green commit**: `c4a6688` (Phases 1–10b CI verified).

## Completed

See [PHASE-STATUS.md](PHASE-STATUS.md): Foundation through Monetization (10b).

## In progress

Phases 11/12 — cloud deployment (Render blueprint, Supabase docs, preflight,
jobs trigger, proxy-aware client IP, S3 storage) and local PC migration
(backup/restore/export/import scripts, production overlay rehearsal CI job).
Pushed in one commit; waiting for CI.

## Next actions (in order)

1. Get the `production` CI job green; record Phase 11/12 checkpoints.
2. Final security audit (fix critical/high); SECURITY.md, DATA_MODEL.md;
   README/ARCHITECTURE/ROADMAP/CHANGELOG refresh.
3. Automated 16-step E2E scenario in CI.
4. Final report.

## Local tooling notes

Only ruff, black, pytest (without app deps) and prettier run locally; mypy,
the backend test-suite and the frontend build run only in CI. The shell has
no brace expansion — create directories one by one.

## Known failures

None on `main`.
