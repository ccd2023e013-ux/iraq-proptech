# Execution state

Read this first when resuming work in a new session.

- **Repository**: `ccd2023e013-ux/iraq-proptech`, branch `main`
- **Verification authority**: GitHub Actions (`.github/workflows/ci.yml`).
  Job logs cannot be downloaded from the development environment; failures
  are republished as check-run annotations by `scripts/ci/annotate.sh`
  (`gh api repos/<repo>/check-runs/<id>/annotations`).
- **Last green commit**: `088419e` — CI run 37019370137 (backend 240 tests,
  91 % coverage; frontend 74 tests; Docker stack + auth/listing/map smoke).

## Completed

See [PHASE-STATUS.md](PHASE-STATUS.md): Foundation, Auth + RBAC, Real estate
core, Search + discovery, GIS + maps, discovery gap-fill, CRM, AI,
Admin + moderation.

## In progress

Phase 9 — Automation + notifications (notifications, preferences, outbox,
SMS/push mock channels, signed webhooks with SSRF guard, Celery beat jobs,
admin webhooks/jobs pages). Docs: [AUTOMATION.md](AUTOMATION.md).

## Next actions (in order)

1. Get Phase 9 CI green; record checkpoint.
2. Analytics (privacy-conscious events; admin/agency/agent dashboards).
3. Monetization with payment-provider abstraction and DEMO payment mode.
4. Cloud deployment docs; local PC migration; DATA_MODEL, SECURITY,
   DEPLOYMENT docs; README/ARCHITECTURE/ROADMAP refresh.
5. Final security audit, final E2E, final report.

## Local tooling notes

Only ruff, black, pytest (without app deps) and prettier run locally; mypy,
the backend test-suite and the frontend build run only in CI. The shell has
no brace expansion — create directories one by one.

## Known failures

None on `main`.
