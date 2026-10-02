# Execution state

Read this first when resuming work in a new session.

- **Repository**: `ccd2023e013-ux/iraq-proptech`, branch `main`
- **Verification authority**: GitHub Actions (`.github/workflows/ci.yml`).
  Job logs cannot be downloaded from the development environment; failures
  are republished as check-run annotations by `scripts/ci/annotate.sh`
  (`gh api repos/<repo>/check-runs/<id>/annotations`).
- **Last green commit**: `3fc684f` — CI run 36962496975 (backend 185 tests,
  frontend 64 tests, Docker stack + auth/listing/map smoke tests).

## Completed

See [PHASE-STATUS.md](PHASE-STATUS.md): Foundation, Auth + RBAC, Real estate
core, Search + discovery, GIS + maps.

## In progress

Phase 6 — CRM + leads (backend models/migration `0005`, schemas, events
module written locally; service/router/tests/UI not yet).

## Next actions (in order)

1. Gap-fill from the master directive: saved searches, property comparison
   API, POIs + nearby, exchange-rate abstraction (no hard-coded rates).
2. Finish CRM: service, router, tests, inquiry form, CRM dashboard,
   pipeline, lead detail, tasks, appointments, conversation threads.
3. AI engine (mock provider default), Admin + moderation, Automation +
   notifications + webhooks, Analytics, Monetization (demo payments),
   Cloud deployment docs, Local PC migration, final security audit + E2E.

## Known failures

None on `main`.
