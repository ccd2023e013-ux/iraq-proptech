# Product audit — Iraq PropTech 2.0 baseline

Audit date: 2026-10-05. Sources: repository at `main`, the live deployment
(<https://iraq-proptech-web.onrender.com>), its automated live verification
(*Live site* workflow), and screenshots of the live site taken by the
*Live screenshots* workflow (desktop/phone, Arabic/English, light/dark,
signed-out/signed-in).

## Rating scale

| Grade | Meaning |
| --- | --- |
| **A** | Production-ready: works on the live site, tested, acceptable UX |
| **B** | Functional, but needs UX/product work |
| **C** | Prototype / mock / demo-only (works, but not real data or real service) |
| **D** | Missing |

Honesty notes that apply everywhere: AI text comes from **MockAI** (a
deterministic simulator), all 126 listings are **synthetic DEMO data**, area
polygons are **DEMO squares** (not official boundaries), POIs are **DEMO
places**, payments are **DEMO**, email/SMS/push are **mocked**.

## Critical findings

1. **Sign-in, sign-up, password reset and email verification pages do not
   exist** (`/login`, `/register`, `/forgot-password`, `/reset-password`,
   `/verify-email` all return 404 on the live site). The forms exist in
   `features/auth/` but were never routed. Every "Sign in" link, protected-page
   redirect and emailed link leads to a 404. Earlier acceptance tests used the
   API directly, so this was missed. **Highest priority (Stage 2).**
2. **No dark mode**: the site ignores `prefers-color-scheme`.
3. **Generic design**: dark banner + rows of identical bordered cards; DEMO
   image labels collide with card badges; property page is a stack of bordered
   boxes; dashboards are link grids.
4. **No email delivery** (SMTP not configured): new users cannot verify, so they
   cannot send inquiries, post listings or create an agency profile.

> Update (Stages 1–2, live-verified): findings 1–3 are fixed; finding 4 is
> now stated honestly in the UI and needs an owner SMTP sender (see ROADMAP-2.0).

## Feature classification

### Platform and operations

| Feature | Grade | Evidence / notes |
| --- | --- | --- |
| Deployment (Render web + API, Supabase DB + storage) | A | Live; health/readiness; deploy tracking by commit |
| CI (backend PostGIS tests, frontend tests/build, Docker stack, production rehearsal) | A | 297 + 81 tests; green |
| Live verification (DB audit, acceptance, browser, security, backup/restore) | A | *Live site* workflow, all green |
| Backup / restore / cloud→PC migration | A | Verified against the live database |
| Security baseline (CSP, CSRF, cookies, RBAC, rate limits, SSRF guard, audit log) | A | Audited; live security checks green |
| Background jobs | B | Inline notifications + hourly GitHub cron (no free worker) |
| Redis | D (live) | Not on the free plan; in-memory fallback |
| Observability (error log, audit log) | B | Admin error log; no metrics/alerting |

### Identity and accounts

| Feature | Grade | Notes |
| --- | --- | --- |
| Auth API (register, login, refresh rotation, logout, sessions, reset, verify) | A | Tested, live-verified via API |
| Auth **pages** | **D** | Missing routes (critical finding 1) |
| Email delivery | C | Mock provider; SMTP adapter exists, not configured |
| Phone/OTP | D | — |
| RBAC (7 roles) + object-level policies | A | — |
| Account settings page | B | Works; generic UI |

### Property marketplace

| Feature | Grade | Notes |
| --- | --- | --- |
| Listing CRUD, lifecycle, moderation | A/B | Works live; listing form UX is long and generic |
| Media upload (images/video/documents, sniffing, EXIF strip) | A | Live-verified |
| Demo dataset (126 listings, 7 cities, DEMO images) | C | Synthetic by design, clearly labelled |
| Search (Arabic normalization, filters, sort) | A/B | Works; filter UI dense |
| Natural-language search | B/C | Rule-based parser via MockAI; works for common phrases |
| Favorites, saved searches, alerts | B | Alerts need email to reach users |
| Compare (incl. statistical analysis) | B | Functional, plain table |
| Property page | B | Functional; generic layout; no hero media experience |
| Homepage | B | Generic; no product story |

### Maps and GIS

| Feature | Grade | Notes |
| --- | --- | --- |
| Map search (MapLibre + OpenFreeMap) | B | Works live: clustering, list sync, draw-area; plain styling, no price bubbles, no satellite |
| Boundaries | C | DEMO squares; no official dataset |
| POIs / nearby | C | DEMO places only |
| Radius / polygon / bbox search | A | API + map |
| Satellite, terrain, 3D | D | — |
| Map provider abstraction | B | Style URL abstraction exists; no provider evaluation yet |

### Intelligence

| Feature | Grade | Notes |
| --- | --- | --- |
| AI provider abstraction (mock, Claude, OpenAI, Gemini) | B | Real adapters exist, untested live (no keys) |
| AI summary / listing writer / reply drafts | C | MockAI, labelled as simulation in the UI |
| Price analysis, comparables, investment | B | Real statistics over platform (demo) data; labelled |
| Fact / source / estimate / interpretation / simulation labelling | B | Provider badge + methodology; not yet per-statement |
| Development intelligence, provenance, "Future Iraq" | D | — |
| AI Property Vision (concepts) | D | — |
| Property Media Studio, drone workflow | D | — |
| Market intelligence (time series, trends) | D | Only search stats and listing analytics |
| Social/Meta authorized intelligence | D | — |
| Urban simulation | D | — |

### Business

| Feature | Grade | Notes |
| --- | --- | --- |
| CRM (inquiries → leads, pipeline, tasks, appointments, messages) | B | Works live; UI generic |
| Agencies, agents, invitations | B | Works; minimal UI |
| Notifications (in-app, outbox, webhooks/n8n) | B | In-app works; email/SMS/push mocked |
| Analytics dashboards | B | Works; minimal visuals |
| Billing (provider abstraction, plans, promotions, subscriptions) | C | DEMO payment mode only |
| Entitlements (Free / Professional / Agency / Enterprise) | D | Plans exist; no feature-entitlement layer |
| Transactions / commissions | D | — |
| Admin console | B | Broad coverage; generic UI; no data-quality dashboard, no source management |

### Experience

| Feature | Grade | Notes |
| --- | --- | --- |
| Arabic RTL / English | A/B | Works; typography adequate, not refined |
| Responsive / mobile | B | No horizontal scroll; dense on phone |
| Dark mode | D | — |
| Motion, transitions, skeletons | D | Few loading states, no motion system |
| Design system | C | Tokens for colours/radius only; 6 basic components |
| Accessibility | B | Semantic HTML, focus rings; no audit |
| Mobile apps | D | API is app-ready (bearer tokens, JSON) |

## What is genuinely valuable

The backend (data model, PostGIS search, policies, CRM, AI provider
abstraction with honest labelling, billing abstraction), the security posture,
and the operations tooling (CI, live verification, backup/restore) are solid
foundations. Stage 2.0 work is mostly **experience**, **auth pages**, and
**new intelligence modules** built on these foundations — not a rebuild.
