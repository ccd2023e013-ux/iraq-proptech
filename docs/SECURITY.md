# Security

Security model, controls and the final pre-release audit. Report
vulnerabilities privately to the repository owner (not in public issues).

## Controls

| Area | Control | Where / test |
| --- | --- | --- |
| Passwords | Argon2id; minimum length, common-password and email-in-password rules; constant-time verification; rehash on parameter change | `auth/security.py`, `test_auth.py` |
| Sessions | 15-minute JWT access token + rotating opaque refresh token (stored as SHA-256); reuse of a used refresh token revokes the whole session; "sign out everywhere"; suspension revokes all sessions | `auth/service.py`, `test_auth.py` |
| Cookies | `HttpOnly` access/refresh cookies, `Secure` in production, `SameSite=Lax`; CSRF double-submit (`X-CSRF-Token` = `csrf_token` cookie) on every cookie-authenticated unsafe request | `auth/cookies.py` |
| Email verification / reset | Single-use hashed tokens with TTL, row-locked on use; reset revokes sessions; no account enumeration | `auth/service.py` |
| Authorization | RBAC permissions per role with rank-based grant rules (SUPER_ADMIN only via CLI); object-level rules centralised in `policies.py` and per-module services; unauthorised objects answer 404 | `test_rbac.py`, `test_crm.py`, `test_properties.py`, … |
| Rate limiting | Redis sliding windows (in-memory fallback) on login, register, verify, reset, inquiries, messages, public AI, view beacons; per-IP and per-identifier | `core/rate_limit.py`, `test_rate_limit.py` |
| Client IP | `X-Forwarded-For` trusted only for `TRUSTED_PROXY_HOPS` proxies | `core/client_ip.py`, `test_security_units.py` |
| Input | Pydantic models with `extra="forbid"`, length limits, enumerations; SQL only through SQLAlchemy expressions or bound parameters (no string-built SQL) | — |
| Uploads | Size limits per kind; content sniffed from bytes (Pillow for images, signatures for PDF/video); images re-encoded and EXIF stripped; decompression-bomb limit; storage keys generated server-side | `properties/uploads.py`, `test_media.py` |
| File serving | Media/documents streamed by the API after authorization, with `nosniff`, `CSP: default-src 'none'; sandbox`; documents as attachments; private bucket | `properties/router.py` |
| Location privacy | Exact coordinates only for managers/moderators; public `display_location` coarsened | `test_gis.py` |
| Webhooks (SSRF) | https only, public hosts only (DNS resolved and checked against private/loopback/link-local ranges at send time), no redirects, HMAC-signed bodies; relaxations are explicit flags | `notifications/webhooks.py`, `test_notifications.py` |
| Open redirects | `next` parameters accepted only as same-origin relative paths | `lib/auth/routing.ts` + tests |
| API proxy | Next.js proxy forwards only `/api/v1/*`, rejects encoded separators and dot segments, strips hop-by-hop headers | `lib/api/proxy.ts` + tests |
| Headers | API: CSP `default-src 'none'`, `nosniff`, `frame-ancestors 'none'`, HSTS in production. Web: CSP, `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy | `core/middleware.py`, `next.config.ts`, `scripts/deploy/smoke.sh` |
| Secrets | Only in environment variables; none in the repository or frontend bundle; production refuses a weak `JWT_SECRET`; logs redact keys that look like secrets | `core/config.py`, `core/logging.py` |
| Production hardening | `/docs`, OpenAPI and dev tools disabled; preflight refuses wildcard/http CORS, insecure cookies, providers without credentials; API bound to `127.0.0.1` | `core/preflight.py` |
| Audit | Append-only `audit_logs` for auth events, role changes, suspensions, moderation, payments, settings, webhooks | `audit/service.py` |
| AI | Provider keys server-side only; prompts built from declared facts; outputs validated against schemas; per-user daily limit; every generation logged | [AI.md](AI.md) |
| Payments | DEMO mode moves no money; demo refused in production unless explicitly enabled; payment completion row-locked and idempotent | `billing/service.py`, `test_billing.py` |

## Final audit (Phase 13)

Method: manual review of every router and service against the checklist
below, targeted code searches, and new automated checks. Severity uses
impact × exploitability for this deployment.

| # | Category | Finding | Severity | Status |
| --- | --- | --- | --- | --- |
| 1 | Rate limiting / DoS | Behind the frontend proxy and Render's edges every user shared the proxy's IP, so one client could exhaust the login/register limits for everyone (and audit logs recorded the proxy IP) | High | **Fixed** — `TRUSTED_PROXY_HOPS`, proxy passes `X-Forwarded-For` unchanged; tests |
| 2 | Headers / XSS defence-in-depth | Web pages had no Content-Security-Policy | Medium | **Fixed** — CSP (no plugins, no framing, `base-uri`/`form-action` self, scripts only from self + MapLibre RTL plugin); smoke test asserts it |
| 3 | Path traversal via proxy | Encoded `..%2F` sequences were forwarded to the API unchanged (no exploitable route found, since FastAPI does not normalise dot segments) | Low | **Fixed** — proxy rejects encoded separators and dot segments; unit tests |
| 4 | Performance / locking | Foreign keys without supporting indexes cause sequential scans and long locks on parent deletes | Low | **Fixed** — the new test `test_every_foreign_key_is_indexed` found 36; migration `0013` indexes them all, and any future gap fails CI |
| 5 | Race | Two simultaneous inquiries by the same customer on the same listing can create two open leads (the lead "reuse" check is not locked) | Low | **Accepted** — rate-limited, no security impact; duplicate leads can be closed by the agent. Fix candidate: `INSERT … ON CONFLICT` + row lock on the customer |
| 6 | Configuration | Production could start with wildcard CORS, insecure cookies or providers lacking credentials | Medium | **Fixed** — preflight errors stop the API |
| 7 | Data exposure | Exact coordinates, documents, unpublished listings, leads, conversations, payments, notifications | — | Verified: object-level checks everywhere; non-owners receive 404 |
| 8 | Privilege escalation | Role grant/revoke, agency membership, agent assignment, moderation | — | Verified: rank checks, SUPER_ADMIN not grantable via API, agents can only assign themselves, invitations bound to the invitee |
| 9 | SQL injection | All queries | — | Verified: no string-built SQL in the codebase |
| 10 | XSS | React escaping; no `dangerouslySetInnerHTML`; uploads served with sandbox CSP | — | Verified |
| 11 | CSRF | Cookie-authenticated mutations | — | Verified: double-submit token + SameSite=Lax |
| 12 | SSRF | Webhooks, AI, SMS | — | Verified: webhook guard; AI/SMS endpoints come from operator configuration, never from users |
| 13 | Secrets | Repository scan (API key, AWS, Google, GitHub, private key patterns; tracked `.env`/key files) | — | Clean |
| 14 | Tokens | JWT audience/issuer/expiry checked; refresh rotation + reuse detection; one-time tokens hashed | — | Verified |
| 15 | Logging | Request IDs, structured JSON, secret-like keys redacted, no request bodies logged | — | Verified |
| 16 | N+1 queries | Search, map, CRM lists | — | Guarded by query-count tests (`test_search.py`) |

No critical issues were found. All high and medium findings are fixed.

## CI and production secrets

Production secrets (`SUPABASE_DB_URL`, `S3_*`, `DEMO_ACCOUNT_PASSWORD`,
`DEMO_ADMIN_PASSWORD`, `JOBS_*`) exist only as GitHub secrets and Render
environment values. Rules for the workflows that use them:

- **Only code on `main` runs with them.** `live.yml` admits a `workflow_run`
  only when CI ran for a `push` to `main` of this repository
  (`workflow_run.event`, `head_branch` and `head_repository.full_name` are all
  checked — a branch filter alone is not enough, because a fork pull request
  can come from a branch called `main` and CI runs for pull requests). Schedule
  and manual runs, and the manual `live-ops`, `live-screenshots` and
  `scheduled-jobs` workflows, run their secret-bearing job only on
  `refs/heads/main`.
- **The gate runs trusted code.** `live.yml`'s `config` job checks out `main`,
  never the commit named in the event, proves that commit is already on `main`
  (`git merge-base --is-ancestor`), and reads `deploy/live.env` as data (no
  `source`); the URLs must be plain `https://` origins.
- **Least privilege.** Workflows default to `permissions: {}`; each job asks for
  `contents: read` (only `live-screenshots` may write, to push its screenshot
  branch). Secret-bearing jobs check out with `persist-credentials: false`.
  Workflow inputs reach shell scripts through environment variables, not
  `${{ }}` interpolation.
- `ci.yml` (which runs for pull requests, including from forks) uses no secrets.

Demo accounts: the shared `DEMO_ACCOUNT_PASSWORD` is never an admin password.
In production the demo admin exists only with its own `DEMO_ADMIN_PASSWORD`
(policy-checked, different from the shared one); without it, the start-up seed
creates no demo admin and disables an existing one (ADMIN role removed,
password replaced, account deactivated, sessions revoked).

Live checks register throw-away accounts on the deployed site with random
per-run credentials (CSPRNG; never printed or passed on a command line) and
suspend them through the demo admin when the run ends, on success or failure.

## Residual risks and operator duties

- `'unsafe-inline'` scripts are allowed because Next.js hydration uses inline
  scripts; moving to nonce-based CSP is a future hardening step.
- HSTS for the web origin should be set by the TLS terminator (Cloudflare,
  Caddy) — the app cannot know whether it is served over HTTPS.
- Run behind exactly the configured number of proxies (`TRUSTED_PROXY_HOPS`).
- Keep `.env` and backups encrypted at rest; rotate `JWT_SECRET` (signs out
  everyone) and provider keys if a machine is compromised.
- Dependency updates: review Dependabot/`pip-audit`/`npm audit` output
  regularly (not automated in CI yet).
