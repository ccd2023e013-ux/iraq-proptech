# Notifications, background jobs and automation

Status: **IMPLEMENTED + TESTED** (`backend/tests/test_notifications.py`, smoke step 17).
SMS and Web Push run in **MOCK** mode by default; a real SMS gateway **REQUIRES EXTERNAL
CREDENTIALS**. n8n is **optional** and never required by the application.

## How it fits together

```
domain change ──► events.emit(name, payload)        (same DB transaction)
                     │
                     ├─ handlers.py ─► Notification (in-app) + NotificationDelivery rows (email/SMS/push outbox)
                     └─ "*" handler ─► WebhookDelivery rows for subscribed endpoints
commit ──► after-commit hook ──► Celery task "notifications.deliver"   (or inline if NOTIFICATIONS_INLINE=true)
beat (every 60 s) ──► "notifications.deliver" again — picks up anything the kick missed
```

* A notification exists **if and only if** the change it describes was committed: rows are
  written in the producing transaction; delivery happens afterwards from the outbox.
* Handlers run inside a SAVEPOINT; a failing handler is logged and never breaks the request.
* Deliveries retry with exponential backoff (max 5 attempts) and are marked `FAILED` after that.
  Webhook endpoints are auto-disabled after 20 consecutive failures.
* `dedupe_key` (partial unique index) makes reminders and saved-search alerts idempotent, so
  re-running a job never double-notifies.

## In-app notifications and preferences

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/me/notifications[?unread_only=true]` | paginated list |
| `GET /api/v1/me/notifications/unread-count` | `{ "unread": n }` (header bell) |
| `POST /api/v1/me/notifications/{id}/read`, `POST …/read-all` | mark read |
| `GET/PUT /api/v1/me/notification-preferences` | per category × channel (in-app, email, SMS, push) |
| `POST/DELETE /api/v1/me/push-subscriptions` | store a browser push subscription |

Categories: `leads`, `messages`, `listings`, `saved_searches`, `reminders`, `reports`, `account`.
Notification text is stored in Arabic and English; the UI shows the user's locale.

## Channels

| Channel | Default | Real mode |
| --- | --- | --- |
| In-app | always on | — |
| Email | `EMAIL_PROVIDER=mock` (outbox) | `EMAIL_PROVIDER=smtp` + `SMTP_*` settings |
| SMS | `SMS_PROVIDER=mock` (records only) | `SMS_PROVIDER=http` + `SMS_GATEWAY_URL` + `SMS_GATEWAY_TOKEN`: POSTs `{"to","text"}` with `Authorization: Bearer` — works with most Iraqi/regional SMS gateways via a tiny adapter |
| Web Push | mock (records only) | FUTURE INTEGRATION (VAPID keys) |

The mock outbox is visible in development at `GET /api/v1/dev/deliveries` (disabled in production).

## Scheduled jobs (Celery beat)

| Job | Schedule | What it does |
| --- | --- | --- |
| `notifications.deliver` | every 60 s | drain the notification + webhook outboxes |
| `jobs.saved_search_alerts` | INSTANT every 10 min, DAILY 06:00, WEEKLY Sat 06:30 (UTC) | counts listings published since the last alert and notifies |
| `jobs.reminders` | every 5 min | due lead follow-ups and CRM tasks (deduplicated) |
| `jobs.expire_listings` | hourly | approved listings past `expires_at` → `EXPIRED` (+ `listing.expired` event) |

Every run is recorded in `job_runs` and shown at **Admin → Background jobs** (`/admin/jobs`).
The worker embeds beat when `WORKER_BEAT=1` (default) — run **exactly one** such worker, or run
`beat` as its own container role and set `WORKER_BEAT=0` on workers.

Without any worker (e.g. a single free container) set `NOTIFICATIONS_INLINE=true`: deliveries
run in the API process right after commit. Scheduled jobs then need an external scheduler to
call the CLI (`python -m app.cli …`) or must wait until a worker is available.

## Webhooks (n8n, Zapier-style tools, your own services)

Admins with `automation.manage` manage endpoints at **Admin → Webhooks** (`/admin/webhooks`) or
via `/api/v1/admin/webhooks` (CRUD, `/test`, `/deliveries`, `/events`).

Events: `listing.created`, `listing.updated`, `listing.published`, `listing.rejected`,
`listing.suspended`, `listing.expired`, `listing.reported`, `lead.created`, `lead.assigned`,
`lead.status_changed`, `inquiry.created`, `message.created`, `appointment.scheduled`,
`report.created`, `report.resolved`, `user.registered`, or `*` for all.

Request:

```
POST <your url>
Content-Type: application/json
X-PropTech-Event: lead.created
X-PropTech-Delivery: <uuid>            # unique per delivery; use it to de-duplicate retries
X-PropTech-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>." + raw body)>

{"event":"lead.created","occurred_at":"2026-10-03T08:00:00+00:00","data":{"lead_id":"…","property_id":"…"}}
```

Payloads carry **identifiers, not personal data**; fetch details through the API with a
scoped account if a workflow needs them. Any 2xx response counts as delivered.

Verifying the signature (Python):

```python
import hashlib, hmac, time

def verify(secret: str, raw_body: bytes, header: str, tolerance: int = 300) -> bool:
    fields = dict(p.split("=", 1) for p in header.split(","))
    ts = int(fields["t"])
    if abs(time.time() - ts) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, fields["v1"])
```

The signing secret is shown **once** when the endpoint is created; store it in your
automation tool's credential store.

### SSRF protection

Webhook URLs must be `https` on a public host. Private, loopback, link-local and reserved
addresses are rejected at creation **and** before every delivery; redirects are not followed;
credentials in URLs are rejected. For local n8n on the same Docker network the development
compose file sets `WEBHOOK_ALLOW_HTTP=true` and `WEBHOOK_ALLOW_PRIVATE_HOSTS=true` —
never enable these in production. Residual risk: DNS rebinding between the check and the
connection; mitigate in production by egress firewalling the worker.

### Optional n8n

```
docker compose --profile automation up -d      # starts n8n on http://localhost:5678
```

1. In n8n create a workflow with a **Webhook** trigger (POST) and copy its production URL
   (`http://n8n:5678/webhook/<id>` from inside Docker).
2. In **Admin → Webhooks** create an endpoint with that URL and the events you want.
3. Click **Send test** — n8n receives a `webhook.test` event.
4. Optional: add a **Code** node that verifies `X-PropTech-Signature` with the snippet above.

If n8n is down, deliveries simply retry and eventually fail; the application is unaffected.
