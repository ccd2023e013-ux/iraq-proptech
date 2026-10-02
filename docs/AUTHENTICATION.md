# Authentication

No third-party identity provider: accounts, passwords and sessions live in
the platform's own PostgreSQL database, so the system runs at $0 and moves
between hosts without changes.

## Accounts

| Field | Notes |
| --- | --- |
| email | Stored lowercased; unique; `EmailStr` validated. |
| phone | Optional. Normalized to E.164 Iraqi mobile (`+9647XXXXXXXXX`); accepts `07xx…`, `+964…`, `00964…`, Arabic-Indic digits. Unique. |
| password | Argon2id (`argon2-cffi` defaults). Policy: 10–128 chars, not a common password, not mostly one character, must not contain the email's local part. |
| status | `ACTIVE`, `SUSPENDED`, `DEACTIVATED`. Non-active accounts cannot sign in and their sessions stop working immediately. |
| roles | `CUSTOMER` always; `PROPERTY_OWNER` can be chosen at sign-up; everything else is granted by an administrator (see [RBAC.md](RBAC.md)). |

## Sessions and tokens

```
login ──► auth_sessions row (sid) ──► access JWT {sub, sid, typ, iss, aud, exp}  (15 min)
                                  └─► refresh token (opaque, 256-bit, SHA-256 stored)  (30 days)
```

- **Access token**: HS256 JWT, algorithm pinned on decode (rejects `none` and
  algorithm confusion), audience/issuer checked. Every request also checks the
  `auth_sessions` row, so logout, suspension and password changes take effect
  instantly — not when the JWT expires. Roles are *not* in the token;
  permissions are resolved from the database on each request.
- **Refresh token**: single-use. `/auth/refresh` consumes it under a row lock
  and issues a new one (rotation). Presenting an already-used token revokes
  the whole session (reuse detection ⇒ likely theft).
- **Revocation**: logout (one session), logout-all, revoke a listed session,
  password change (all other sessions), password reset (all sessions),
  suspension (all sessions).

### Transports

| Client | How tokens travel |
| --- | --- |
| Browser (default) | httpOnly `access_token` and `refresh_token` cookies, `SameSite=Lax`, `Secure` in production. Tokens never appear in response bodies or JavaScript. |
| Mobile app / integration | Send `X-Auth-Transport: bearer` to login/refresh to receive tokens in the body; then `Authorization: Bearer <access>`. |

### CSRF

Cookie-authenticated **unsafe** requests (POST/PUT/PATCH/DELETE) must send
`X-CSRF-Token` equal to the readable `csrf_token` cookie (double-submit),
on top of SameSite=Lax. Bearer requests are exempt (not sent automatically by
browsers). The web client adds the header automatically.

## Verification and password reset

`verification_tokens` stores SHA-256 hashes of single-use tokens:

| Purpose | Lifetime | Notes |
| --- | --- | --- |
| `EMAIL_VERIFY` | 48 h | Issuing a new one invalidates older ones. Fails if the email changed since. |
| `PASSWORD_RESET` | 30 min | `/password/forgot` always answers 202 (no account enumeration). Reset revokes all sessions. |
| `PHONE_VERIFY` | — | Schema ready; SMS delivery arrives with the notification providers (Phase 9). |

Emails go through the email provider interface. The default **MOCK**
provider sends nothing: it logs the message and keeps it in memory. In
development (`APP_ENV != production`) the captured messages are available at
`GET /api/v1/dev/outbox` — this router is never mounted in production.

## Rate limits

Redis fixed windows (falls back to in-memory if Redis is down). Keys are
hashes — no raw emails or IPs are stored in Redis.

| Endpoint | Per IP | Per account |
| --- | --- | --- |
| `POST /auth/login` | 20 / 5 min | 10 / 15 min |
| `POST /auth/register` | 10 / hour | — |
| `POST /auth/password/forgot` | 10 / hour | 3 / hour |
| `POST /auth/password/reset` | 20 / hour | — |
| `POST /auth/verify-email` | 30 / hour | — |
| `POST /auth/resend-verification` | 5 / hour | — |
| `POST /auth/refresh` | 60 / 5 min | — |

Client IP comes from the TCP peer; behind a reverse proxy set
`FORWARDED_ALLOW_IPS` to the proxy's address so uvicorn trusts
`X-Forwarded-For`.

## Endpoints

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | — |
| POST | `/api/v1/auth/login` | — |
| POST | `/api/v1/auth/refresh` | refresh cookie + CSRF, or body token |
| POST | `/api/v1/auth/logout` | refresh cookie + CSRF, or body token |
| POST | `/api/v1/auth/logout-all` | user |
| GET | `/api/v1/auth/me` | user |
| POST | `/api/v1/auth/verify-email` | — (token) |
| POST | `/api/v1/auth/resend-verification` | user |
| POST | `/api/v1/auth/password/forgot` | — |
| POST | `/api/v1/auth/password/reset` | — (token) |
| POST | `/api/v1/auth/password/change` | user |
| GET | `/api/v1/auth/sessions` | user |
| DELETE | `/api/v1/auth/sessions/{id}` | user (own sessions only; others → 404) |
| PATCH | `/api/v1/users/me` | user |

## Web application

- `src/middleware.ts` guards `/dashboard`, `/account`, `/admin`, `/favorites`,
  `/messages` by cookie *presence*: no cookies → `/login?next=…`; only the
  refresh cookie left → `/auth/refresh?next=…`, which renews the session
  server-side and returns the user to the page. The API still makes every
  authorization decision.
- `next` parameters are sanitized (`safeNextPath`) — only same-site relative
  paths, so login cannot be abused as an open redirect.
- Client requests renew an expired session once (single-flight) and retry.

## Operations

Create the first super administrator (never possible through the API):

```bash
cd backend
SUPERADMIN_PASSWORD='…' .venv/bin/python -m app.cli create-superadmin --email you@example.com --name "Your Name"
# Docker: docker compose exec -e SUPERADMIN_PASSWORD='…' backend python -m app.cli create-superadmin --email …
```

Known limitation: two browser tabs refreshing in the very same instant can
trigger reuse detection and sign the user out (both present the same token).
The web client serializes refreshes within a tab; cross-tab coordination can
be added later if it shows up in practice.
