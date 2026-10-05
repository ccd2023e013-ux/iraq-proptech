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

## 2.0 (docs/ROADMAP-2.0.md)

Stages 0–7 done and live-verified (latest Live site run 37306723398 on `c2fa8fe`).
Brand: مَكان | MAKAN (`0dfbb95`) — deployed by Render; CI/live run blocked (below).
Stage 8 (Market Intelligence) is built and statically audited on branch
`stage-8-market` (PR #1, docs/STAGE-8-AUDIT.md on that branch) and is NOT
merged. Stage 9 must not start until Stage 8 is fully verified.

**Blocker (2026-10-05 ~13:35 UTC):** GitHub Actions refuses to start jobs
("recent account payments have failed or your spending limit needs to be
increased") — the private repo's free minutes are used up. **Owner decision:
keep the repo private, do not raise spending, wait for the monthly reset.**
The scheduled jobs now run every 3 hours instead of hourly to save minutes.

When Actions is back, follow the "Verification gate" in docs/STAGE-8-AUDIT.md
(on the branch) exactly: branch CI with the 12-combination browser matrix and
stack security → merge only if all pass → Render deploy → full Live site +
`live-probe mode=market` on production → only then Stage 8 COMPLETE, remove
the daily retry, and start Stage 9. Stage 8 is UNVERIFIED until then.

Render still deploys `main` on push without CI, so unverified work stays on
branches until CI is back.

Helpers: `live-probe.yml` with `mode=auth` or `mode=map` runs only those browser checks;
`live-screenshots.yml` with `pages=` pushes JPEGs to `screenshots/run-<id>`.

## Next actions

Owner options: free SMTP sender (public sign-ups), custom domain (+ web HSTS),
production PC migration (MIGRATE-TO-LOCAL-PC.md).

## Local tooling notes

Only ruff, black, pytest (without app deps) and prettier run locally; mypy,
the backend test-suite and the frontend build run only in CI. The shell has
no brace expansion — create directories one by one.

## Known failures

None on `main`.
