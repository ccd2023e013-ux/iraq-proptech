# Monetization

Status: **IMPLEMENTED + TESTED in DEMO PAYMENT MODE** (`backend/tests/test_billing.py`,
smoke step 19). Real payment gateways are **FUTURE INTEGRATIONS** that **REQUIRE MERCHANT
CREDENTIALS** — no real money can be collected by this code today, and nothing in the UI
claims otherwise.

## What can be sold

| Product | Plan kind | Effect |
| --- | --- | --- |
| Listing promotion | `PROMOTION` | the listing is featured for `duration_days` (consecutive purchases extend the period) |
| Subscription | `SUBSCRIPTION` | `featured_credits` per period; each credit features one listing for 7 days |

Promoted listings are **always labelled** «إعلان مُروَّج» / "Promoted" on cards and appear in the
home-page promoted section (`GET /api/v1/properties/featured`). Promotion never changes search
ranking silently, and never alters listing facts.

Prices are **not hard-coded**. Super administrators (`billing.manage`) create plans in
**Admin → Billing**. Once created a plan's price is immutable (payments reference it); create a
new plan and deactivate the old one. `python -m app.cli seed-demo` adds two clearly labelled
DEMO plans with example prices.

## Flow

```
POST /billing/checkout {plan_code, property_id?} ─► Payment PENDING + provider checkout
        └─ redirect_url (same-site only) ─► provider page
provider outcome ─► service.complete(payment) — row-locked, idempotent:
        SUCCEEDED → Subscription (one ACTIVE per user, unique index) or Promotion (+ properties.featured_until)
        FAILED    → nothing is granted
admin refund ─► REFUNDED, promotions withdrawn, subscription canceled, audited
beat: jobs.expire_subscriptions (hourly) → EXPIRED / CANCELED at period end (no auto-renewal in demo)
```

Every money-relevant action is audited (`billing.checkout`, `billing.payment_succeeded`,
`billing.payment_refunded`, `billing.plan_created`, `billing.plan_updated`,
`billing.credit_redeemed`, `billing.subscription_cancel_requested`) and `payment.succeeded`
is published to webhooks.

## Providers

`app/billing/providers.py` defines `PaymentProvider` (`create_checkout`, `parse_callback`,
`refund`).

| `PAYMENT_PROVIDER` | Behaviour |
| --- | --- |
| `demo` (default) | in-app simulated checkout at `/billing/demo/{payment}` with "simulate success / decline"; every record has `is_demo=true`; pages show a DEMO banner; demo revenue is reported separately from real revenue |
| `none` | billing disabled — checkout returns `503 BILLING_DISABLED` |

In production `demo` is **forced to `none`** unless `PAYMENT_DEMO_IN_PRODUCTION=true` is set
deliberately (e.g. a public demo site).

### Adding a real gateway (future)

Candidates for Iraq: ZainCash, FIB (First Iraqi Bank), Qi Card / Super Qi, international card
processors. Each needs a merchant agreement and credentials, which must be stored as secrets,
never committed. Implementation outline:

1. Implement `PaymentProvider` for the gateway: hosted checkout URL creation and **signature
   verification** of callbacks.
2. Add a callback route that calls `parse_callback` then `service.complete(...)` (already
   idempotent and row-locked; repeated callbacks are harmless).
3. Add the provider name to `payment_provider` and document required environment variables.
4. Reconcile settlements against `billing_payments.provider_ref` (unique per provider).

Legal/tax decisions (VAT/invoicing, refund policy, terms of sale) are business decisions that
must be made by the operator before enabling real payments.

## API summary

Public: `GET /billing/config`, `GET /billing/plans`, `GET /properties/featured`.
Signed-in: `POST /billing/checkout`, `GET /billing/payments/{id}` (payer only),
`POST /billing/payments/{id}/demo-complete` (payer, demo only), `GET /me/billing`,
`POST /me/subscription/cancel`, `POST /billing/promotions/redeem`.
Super admin: `GET/POST/PATCH /admin/billing/plans`, `GET /admin/billing/payments`,
`POST /admin/billing/payments/{id}/refund`, `GET /admin/billing/summary`.
