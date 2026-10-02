# Data model

PostgreSQL 16 + PostGIS 3.4 (`pg_trgm` for fuzzy Arabic search). The schema
is owned by Alembic (`backend/alembic/versions`); the test
`test_models_match_migrations` fails if a SQLAlchemy model and the migrations
diverge, and `test_every_foreign_key_is_indexed` fails if a foreign key has no
supporting index. Field-level detail lives in the models
(`backend/app/<module>/models.py`); this page is the map.

## Conventions

| Convention | Rule |
| --- | --- |
| Keys | UUID primary keys (`uuid4`), except reference tables keyed by a stable `code` (`roles`, `property_types`, `amenities`, `lead_statuses`, `billing_plans.code` unique) |
| Time | `timestamptz`, stored in UTC; analytics days use `ANALYTICS_UTC_OFFSET_MINUTES` (Iraq = UTC+3) |
| Money | `numeric(18,2)` + ISO currency (`IQD`, `USD`); never floats. Conversions use `exchange_rates`, and searches never convert silently |
| Geometry | `geometry(Point, 4326)` for listings/POIs, `geometry(MultiPolygon, 4326)` for boundaries; GiST indexes; distances via `geography` casts |
| Arabic text | Generated `search_vector` (tsvector over normalized Arabic: hamza/alef/ya/ta-marbuta folding, tatweel and diacritics removed) + trigram indexes |
| Soft delete | `deleted_at` on users, agencies, properties (rows kept for history and audit) |
| Demo data | `is_demo` on properties/plans/payments, shown as DEMO in the UI, excludable from search and map |
| Secrets | Tokens are stored only as SHA-256 hashes; passwords as Argon2id hashes |

## Entity groups

```
users ─┬─ user_roles ── roles
       ├─ auth_sessions ── refresh_tokens          (rotation + reuse detection)
       ├─ verification_tokens                      (email verify / password reset)
       ├─ agency_members ── agencies ── agency_invitations
       │        └─ agent_profiles
       ├─ favorites ── properties
       ├─ saved_searches
       ├─ notifications, notification_preferences, notification_deliveries, push_subscriptions
       └─ billing_subscriptions / billing_payments ── billing_plans
                                                    └─ billing_promotions ── properties

governorates ── cities ── districts ── neighborhoods        points_of_interest
      └──────────────┴─────────┴──────────────┴── properties

properties ─┬─ property_media, property_documents (private)
            ├─ property_amenities ── amenities;  property_types
            ├─ property_price_history, property_status_history, property_verifications
            ├─ inquiries ── crm_leads ─┬─ crm_lead_activities
            │                          ├─ crm_appointments, crm_tasks
            │                          ├─ lead_statuses
            │                          └─ crm_customers
            ├─ conversations ── messages
            ├─ reports (moderation)
            └─ property_view_daily / property_view_visitors (analytics)

audit_logs  ai_generations  search_stats_daily  exchange_rates  system_settings
webhook_endpoints ── webhook_deliveries   job_runs   error_events
```

## Tables by module

| Module | Tables | Notes |
| --- | --- | --- |
| users / rbac | `users`, `user_roles`, `roles` | Roles: SUPER_ADMIN, ADMIN, MODERATOR, AGENCY_OWNER, AGENT, PROPERTY_OWNER, CUSTOMER (see [RBAC.md](RBAC.md)) |
| auth | `auth_sessions`, `refresh_tokens`, `verification_tokens` | [AUTHENTICATION.md](AUTHENTICATION.md) |
| agencies | `agencies`, `agency_members` (one agency per user), `agency_invitations`, `agent_profiles` | Agency status PENDING/VERIFIED/REJECTED/SUSPENDED |
| geo | `governorates` (19), `cities`, `districts`, `neighborhoods`, `points_of_interest` | Boundaries are DEMO until official data is loaded ([GIS.md](GIS.md)) |
| properties | `properties`, `property_types`, `amenities`, `property_amenities`, `property_media`, `property_documents`, `property_price_history`, `property_status_history`, `property_verifications` | `location` (exact, private) vs `display_location` (public, coarsened per `location_privacy`); `reference_code` per governorate sequence |
| search | `saved_searches`, `favorites` | Saved searches drive instant/daily/weekly alerts |
| crm | `inquiries`, `crm_leads`, `lead_statuses`, `crm_lead_activities`, `crm_appointments`, `crm_tasks`, `crm_customers`, `conversations`, `messages` | Lead visibility: assignee, agency owner, admins ([CRM.md](CRM.md)) |
| moderation | `reports`, `error_events` | |
| notifications / automation | `notifications`, `notification_preferences`, `notification_deliveries` (outbox), `push_subscriptions`, `webhook_endpoints`, `webhook_deliveries`, `job_runs` | [AUTOMATION.md](AUTOMATION.md) |
| ai | `ai_generations` | Every generation logged with provider, model, inputs hash, confidence ([AI.md](AI.md)) |
| analytics | `property_view_daily`, `property_view_visitors`, `search_stats_daily` | Aggregates only; visitor keys are salted hashes purged after the day ([ANALYTICS.md](ANALYTICS.md)) |
| billing | `billing_plans`, `billing_payments`, `billing_subscriptions`, `billing_promotions` | Provider abstraction; DEMO mode ([MONETIZATION.md](MONETIZATION.md)) |
| money | `exchange_rates` | Admin-maintained, dated |
| system / audit | `system_settings`, `audit_logs` | Audit log is append-only from the application |

## Integrity rules enforced in the database

- Unique: user email (stored lower-case, enforced by a check constraint),
  phone, one agency membership per user, one favorite per (user, property),
  one daily analytics row per (property, day), one active subscription per
  user, (provider, provider reference) per payment, listing reference codes.
- About 70 check constraints: enumerated statuses, non-negative money and
  credits, and similar invariants. Coordinates are additionally validated in
  the API (Iraq bounding box).
- Foreign keys: `CASCADE` for owned children (media, history, activities,
  memberships), `SET NULL` for optional references (assignee, actor), and
  `RESTRICT` for reference data (governorates, cities, property types) so
  history is never silently deleted.

## Backups and portability

Backups and cloud→PC moves are **data-only** dumps of the `public` schema
plus the Alembic revision; the schema is always rebuilt by the migrations
([MIGRATE-TO-LOCAL-PC.md](MIGRATE-TO-LOCAL-PC.md)).
