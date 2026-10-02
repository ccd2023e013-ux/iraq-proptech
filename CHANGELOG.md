# Changelog

All notable changes, newest first. Each entry lists the CI-verified commit.

## Phase 8 — Admin + moderation (`088419e`)
Listing/user reports, moderation reason codes, review queues, admin console
(overview, moderation, reports, verification, users, audit, AI usage,
settings, system/errors), typed runtime settings, site announcement.

## Phase 7 — AI (`088419e`)
Provider abstraction (mock default; Claude/OpenAI/Gemini with keys), fact
guards, explainable price estimates, NL search, authoring assistant, reply
drafts, lead prioritisation, usage limits and logging.

## Phase 6 — CRM + leads (`088419e`)
Inquiries, leads with agency scoping, pipeline, notes, tasks, appointments,
conversation threads, CRM dashboard and messages UI.

## Phase 5b — Discovery gap-fill (`683d92a`)
Saved searches, property comparison, POIs + nearby, exchange-rate
abstraction with indicative conversion.

## Phase 5 — GIS + maps (`3fc684f`)
Map GeoJSON with server clustering, boundaries API, point resolution, admin
boundary management, labelled DEMO seed, MapLibre map search page, location
picker, map provider abstraction.

## Phase 4 — Search + discovery (`ef5a719`)
Arabic-normalized full-text + trigram search, structured and spatial filters,
sorting, favorites, landing/results/detail/favorites pages.

## Phase 3 — Real estate core (`ee0b8c8`)
Locations, property types, amenities, agencies, listings lifecycle, media and
documents with safe image processing, verification, listing management UI.

## Phase 2 — Authentication + RBAC (`ec0c09d`)
Argon2id, JWT + rotating refresh tokens, cookies + CSRF, email verification,
password reset, sessions, roles and permissions, audit log, rate limiting.

## Phase 1 — Foundation (`c989590`)
Monorepo, Docker Compose, FastAPI, PostGIS, Redis, Celery, Next.js RTL, CI.
