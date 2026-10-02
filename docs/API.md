# HTTP API

Base path: `/api/v1`. Outside production the OpenAPI schema is served at
`/api/v1/openapi.json` and interactive docs at `/docs` on the API host; both
are disabled when `APP_ENV=production`.
The web app calls the API through its same-origin proxy (`/api/...` on the
frontend origin), so browsers never talk to the API host directly.

## Conventions

- **JSON** everywhere except uploads (`multipart/form-data`).
- **Errors** use one envelope:
  `{"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}`.
  `code` is stable and machine-readable (the web app translates it);
  `request_id` matches the `X-Request-ID` response header and the logs.
- **Pagination**: `?page=1&page_size=20` (max 100). Responses are
  `{"items": [...], "total": n, "page": p, "page_size": s}`.
- **Authentication**: httpOnly cookies + `X-CSRF-Token` header for browsers,
  or `Authorization: Bearer` with `X-Auth-Transport: bearer` at login for
  other clients. See [AUTHENTICATION.md](AUTHENTICATION.md).
- **Authorization**: permission checks per endpoint plus object-level
  policies. See [RBAC.md](RBAC.md). Objects the caller may not see return
  `404` (not `403`) to avoid leaking their existence.
- **Money** is always returned with its original currency (`IQD` or `USD`);
  the API never converts between currencies.
- **Rate limits** return `429` with `Retry-After`.

## Endpoint groups

| Group                 | Endpoints                                                                                                                                                                                                                                                                                       |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | --------------- |
| Health                | `GET /health`, `GET /health/ready`                                                                                                                                                                                                                                                              |
| Auth                  | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/logout-all`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/password/forgot`, `/auth/password/reset`, `/auth/password/change`; `GET /auth/me`; `GET/DELETE /auth/sessions[/{id}]`                      |
| Users / admin         | `PATCH /users/me`; `GET /admin/users[/{id}]`; `POST /admin/users/{id}/suspend                                                                                                                                                                                                                   | reactivate`; `PUT/DELETE /admin/users/{id}/roles/{role}`; `GET /admin/audit-logs`; `GET /rbac/roles` |
| Reference & locations | `GET /reference/property-types`, `/reference/amenities`; `GET /locations/governorates`, `/locations/cities?governorate_id=`, `/locations/districts?city_id=`, `/locations/neighborhoods?district_id=`                                                                                           |
| Agencies & agents     | `GET/POST /agencies`; `GET/PATCH /agencies/{id}`; `POST /agencies/{id}/decision`; members and invitations; `GET /me/agency`; `PUT /agents/me`; `GET /agents/{user_id}`                                                                                                                          |
| Properties            | `POST /properties`; `GET /me/properties`; `GET/PATCH/DELETE /properties/{id}`; lifecycle actions (`submit`, `moderate`, `archive`, `mark-sold`, ...); media (`POST /properties/{id}/media`, ordering, cover, delete, `GET /media/{id}`); private documents; `GET /properties/{id}/verifications | price-history                                                                                        | status-history` |
| Search                | `GET /search/properties`, `POST /search/properties`                                                                                                                                                                                                                                             |
| Favorites             | `PUT/DELETE /properties/{id}/favorite`; `GET /me/favorites`, `/me/favorites/ids`                                                                                                                                                                                                                |
| Development only      | `GET /dev/outbox` (MOCK email outbox; never mounted when `APP_ENV=production`)                                                                                                                                                                                                                  |

## Search

`GET /search/properties` (query string) and `POST /search/properties`
(JSON body with the same fields) return public (approved, non-deleted)
listings as cards.

| Parameter                                                                                                 | Meaning                                                                                                                                                                                                                                                        |
| --------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `q`                                                                                                       | Keyword. Arabic is normalized (أ/إ/آ→ا, ى→ي, ة→ه, diacritics and tatweel removed, Arabic-Indic digits→Latin). Matches full-text search, trigram word similarity (typos), and location names.                                                                   |
| `governorate_id`, `city_id`, `district_id`, `neighborhood_id`                                             | Location filters.                                                                                                                                                                                                                                              |
| `property_types`                                                                                          | Repeatable type code (`APARTMENT`, `HOUSE`, ...).                                                                                                                                                                                                              |
| `purpose`, `rent_period`                                                                                  | `SALE`, `RENT`, ... / `DAILY`, `MONTHLY`, `YEARLY`.                                                                                                                                                                                                            |
| `currency`, `min_price`, `max_price`                                                                      | A price range **requires** a currency; listings in the other currency are excluded, never converted. Price-on-request listings are excluded from price ranges.                                                                                                 |
| `min_area`, `max_area`, `bedrooms_min`, `bathrooms_min`                                                   | Numeric ranges.                                                                                                                                                                                                                                                |
| `amenities`                                                                                               | Repeatable; the listing must have **all** of them.                                                                                                                                                                                                             |
| `furnishing`, `condition`, `verified_only`, `exclude_demo`, `agency_id`, `agent_id`, `posted_within_days` | Further filters.                                                                                                                                                                                                                                               |
| `bbox=w,s,e,n` · `near_lat`,`near_lon`,`radius_km` · `polygon=lon,lat;lon,lat;...`                        | Spatial filters on the **public display location** (never the exact private point).                                                                                                                                                                            |
| `sort`                                                                                                    | `newest` (default), `price_asc`, `price_desc`, `area_desc`, `area_asc`, `relevance` (needs `q`), `distance` (needs `near_*`). Amounts in different currencies are never compared: without a `currency` filter, price sorts group IQD listings first, then USD. |

Unknown parameters are rejected (`422`) instead of silently ignored.
Results are capped at 10,000 per query; cards are loaded in batches (no N+1).
Indexes: GIN on the generated `search_vector` and on `search_text`
(trigram), B-tree on status + price/area/published date, GIST on locations.
