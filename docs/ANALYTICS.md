# Analytics

Status: **IMPLEMENTED + TESTED** (`backend/tests/test_analytics.py`, smoke step 18).

## Principles

* **Aggregates only.** No raw clickstream and no personal data is stored for analytics.
* **Actual activity only.** DEMO listings are excluded by default (`include_demo=true` to show
  them, clearly labelled); AI price estimates are never mixed into analytics.
* **Same authorization model as the rest of the API**: lister → own listings, agency owner →
  agency, admin → platform. Out-of-scope agencies/listings return 404.

## What is measured

| Metric | Source | Definition |
| --- | --- | --- |
| Views | `property_view_daily` | one unique visitor per listing per local day; the lister and assigned agent are not counted |
| Favorites | `favorites.created_at` | favorites added in the range |
| Inquiries | `inquiries.created_at` | inquiries received in the range |
| Leads / won | `crm_leads` | created in range / closed in a "won" stage in range |
| Inquiry rate | inquiries ÷ views | `null` when there are no views |
| Searches | `search_stats_daily` | first-page searches per day × governorate × purpose, and how many returned nothing; **no query text** |
| Agent activity | leads + `crm_lead_activities` | leads assigned, won, activities logged |

Days use `ANALYTICS_UTC_OFFSET_MINUTES` (default 180 — Iraq, UTC+3, no DST).

### Unique-visitor counting without tracking

The listing page sends a beacon (`POST /api/v1/analytics/property-views/{id}`). The server
hashes the visitor key (user id, or IP + user agent for anonymous visitors) with HMAC using a
**per-day salt derived from the server secret**, inserts it into `property_view_visitors`
(primary key = day + listing + hash) and increments the daily counter only on first insert.
Hashes cannot be linked across days, and the table is purged after 2 days by the
`jobs.purge_analytics_visitors` beat task. Behind a reverse proxy set `FORWARDED_ALLOW_IPS`
so the real client address is used for anonymous visitors.

## API

* `GET /api/v1/analytics/overview?scope=me|agency|platform&agency_id=&date_from=&date_to=&include_demo=`
  — default range: last 30 days; at most 366 days. Returns `summary`, `series` (one row per
  day), `listings_by_status`, `leads_by_status`, `top_listings`, `agents` (agency/platform),
  `platform` (searches, zero-result rate, new users, by governorate/purpose) and `data_notes`.
* `GET /api/v1/analytics/properties/{id}` — the same for one listing (its managers and admins).
* `POST /api/v1/analytics/property-views/{id}` — beacon; always `204`, rate limited.

## UI

* `/dashboard/analytics` — "My listings" and, for agency owners, "My agency" (agent table).
* `/admin/analytics` — platform analytics.
Both have a date-range form (works without JavaScript) and an accessible bar chart with a data
table fallback.

## Not included (future)

Traffic sources/referrers, funnel by device, cohort retention, exports. These would need
consent-aware client analytics and are deliberately left out.
