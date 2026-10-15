# MAKAN redesign — recovery audit

Branch `design/premium-redesign`. Audit date 2026-10-14, against the running preview built from commit `8097760`: 144 page captures across Arabic and English, dark and light, at 1920, 1440 and 390 px, signed out, as agent and as admin; the real-browser MapLibre check; and the source.

This document answers three questions before more visual work is done:

1. What did the four briefs ask for, and what state is each requirement in? (§1)
2. Why does the rendered interface still look cheap? (§2)
3. What is the recovery plan, pass by pass? (§3)

## Status key

| Status        | Meaning                                                                                                                          |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Verified**  | Implemented and verified in the running preview: screenshots, the browser check, or an interaction run by the screenshot script. |
| **Partial**   | Some of it exists; what is missing is named.                                                                                     |
| **Missing**   | Not built.                                                                                                                       |
| **Blocked**   | Needs an external service, credential, dataset or capability that this repository does not have. The blocker is named.           |
| **Demo only** | Works, but only as a labelled demonstration: mock provider, demo data or a deterministic renderer.                               |

## Sources

| Brief                                                              | Date       | Short name |
| ------------------------------------------------------------------ | ---------- | ---------- |
| "MAKAN — Premium Visual Redesign + Immediate Live Preview"         | 2026-10-09 | **B1**     |
| "MAKAN — Radical Product Design Transformation"                    | 2026-10-10 | **B2**     |
| Pass 2 instructions (photos, map)                                  | 2026-10-11 | **B3**     |
| "MAKAN — Premium Product Redesign & Missing Requirements Recovery" | 2026-10-14 | **B4**     |

---

## 1. Requirements matrix

### 1.1 Process, preview and safety

| #   | Requirement                                                                              | Source | Status       | Evidence or gap                                                                                                                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------- | ------ | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | Work only on a dedicated branch; `main` untouched; no merge or production deploy         | B1–B4  | **Verified** | All work is on `design/premium-redesign`; nothing has been merged or deployed.                                                                                                                                                                                   |
| P2  | Isolated online preview I can open on my phone, with demo data and no production secrets | B1, B2 | **Verified** | A GitHub-hosted runner runs the Docker stack behind a Cloudflare quick tunnel. Secrets are generated per run; demo logins are published only encrypted. The URL changes on each push and expires after about 5.5 hours.                                          |
| P3  | Don't weaken tests, auth or security; no advisory exemptions                             | B1–B4  | **Verified** | CI frontend, backend and rehearsal jobs are green. No exemptions were added.                                                                                                                                                                                     |
| P4  | Baghdad Stage 8 out of scope; no Stage 9                                                 | B1–B4  | **Verified** | The only red checks are the Stage 8 Baghdad checks, including the market matrix at 24/48. Stage 9 has not been started.                                                                                                                                          |
| P5  | Real-browser checks: RTL/LTR, light/dark, desktop/mobile, console, overflow              | B1, B4 | **Partial**  | **Done:** screenshots and console/overflow logs for every route; the MapLibre check in 8 states. **Gap:** the light theme is only captured for 5 pages, tablet widths are not captured, and keyboard focus and reduced motion are not yet checked automatically. |
| P6  | Before and after screenshots; report what was really verified                            | B1, B2 | **Verified** | Each checkpoint ships screenshots from the preview.                                                                                                                                                                                                              |

### 1.2 Identity and visual system

| #   | Requirement                                                                                                       | Source | Status       | Evidence or gap                                                                                                                                                                                                                                                                             |
| --- | ----------------------------------------------------------------------------------------------------------------- | ------ | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| V1  | Brand مَكان / MAKAN; Arabic tagline                                                                               | B1     | **Verified** | Header, footer and hero.                                                                                                                                                                                                                                                                    |
| V2  | Keep the agreed palette `#0B0F17` / `#161E2E` / `#10B981` / `#06B6D4`, but restrained                             | B1, B2 | **Verified** | R1 restored the agreed navy (`#0B0F17` canvas, `#161E2E` raised) with derived steps, emerald for action and cyan for place. Gold marks uncertainty.                                                                                                                                         |
| V3  | Readex Pro for Arabic, Inter for English, deliberate scale                                                        | B1, B4 | **Partial**  | R1 loads Inter's optical sizes and adds a new display/title/lede/meta/label/KPI scale. The text floor is now 13/14.5 px, and Arabic display is set at weight 520 with more leading. **Gap:** Readex Pro still loads only the weight axis; the HEXP axis is not used yet.                    |
| V4  | Dark mode is the default; light is good too                                                                       | B1, B2 | **Partial**  | Dark is the default. R1 gives light a cool limestone canvas with navy ink. Light is captured for only 5 pages, and the light basemap is still grey (R2).                                                                                                                                    |
| V5  | Tokens for every repeated decision                                                                                | B2     | **Partial**  | Colour, radius and motion are tokens. About 250 legacy `sand-*` / `brand-*` aliases and 150 ad-hoc `text-xs` remain.                                                                                                                                                                        |
| V6  | One icon family, consistent stroke and active states                                                              | B1, B2 | **Verified** | `components/ui/Icon.tsx`, 40 icons, no emoji.                                                                                                                                                                                                                                               |
| V7  | Buttons: hover, press, focus, loading, disabled, success; hierarchy by importance                                 | B1, B2 | **Partial**  | R1 adds one button system (`btn-primary/secondary/quiet/danger`, `btn-sm/lg`), used by `Button` and by 14 converted link buttons. Native checkbox, radio, range and file inputs are styled. **Gap:** a few one-off buttons remain on pages not yet redesigned (detail, compare table, CRM). |
| V8  | Inputs, chips, segmented controls, tooltips, dropdowns, dialogs, filters                                          | B1     | **Partial**  | `.field` (48 px, with a drawn select chevron that mirrors in RTL), `.chip` (now also the listing type filter) and `.seg`. There is no tooltip component yet.                                                                                                                                |
| V9  | Avoid identical cards, pills, big radii, gradients, neon, floating panels, emoji, generic dashboards, empty space | B2, B4 | **Partial**  | Pills, gradients and emoji are gone. **Remaining:** generic dashboard tiles, purposeless empty space, and broadsheet hairlines everywhere (§2).                                                                                                                                             |
| V10 | Arabic RTL must feel native; English LTR excellent                                                                | B2     | **Partial**  | Mirroring is correct. Arabic typographic quality is not there yet (§2.2).                                                                                                                                                                                                                   |
| V11 | Empty, loading, error, success and unavailable states                                                             | B4     | **Partial**  | R1 rebuilt `EmptyState` (large, with an icon, a heading and actions) and uses it in favourites, saved searches, notifications, messages and smart search. Loading, error and unavailable states are unchanged.                                                                              |
| V12 | Tablet behaviour                                                                                                  | B1, B4 | **Partial** | R3: the map has a real tablet layout: a 340 px docked results rail from 768 px, the compact preview card, and zoom controls. The review run captures the map, property, compare, market and assistant pages at 768 px. Other pages use their responsive grids, with no tablet-specific design. R3 review: the header's full navigation now starts at 1024 px; at 768 px it overlapped, so tablets use the menu. |

### 1.3 Pages

| #   | Page or area                                                          | Source | Status       | Evidence or gap                                                                                                                                                                                                                                                       |
| --- | --------------------------------------------------------------------- | ------ | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | Header, navigation, account controls, mobile tab bar, footer          | B1, B2 | **Verified** | R1: a 60/72 px header, a 21 px wordmark, 15 px navigation with an emerald active rule, and a compact footer on the page grid. On phones the theme control moves into the menu sheet so the header no longer collides at 390 px.                                       |
| G2  | Home                                                                  | B1, B2 | **Partial**  | R1: a full-bleed live map hero with price tags and an intro camera move; a lead-plus-four photo section; a market band; the river city index. **Gap:** the hero shows only a few price tags at once (tag density and basemap are R2), and the photo set repeats (R3). |
| G3  | Listings `/properties`                                                | B1, B2 | **Partial**  | Ruled filter column and photo cards. The cards' information hierarchy and photo repetition are weak.                                                                                                                                                                  |
| G4 | Property detail                                                       | B1, B2 | **Verified** (preview) | R3: title band with price; photography first, with the photo stamped as representative on demo listings; a key-facts band; a "What you can rely on" provenance panel (verified, declared, demo, approximate); description; full details; features; documents (declared, not verified unless checked); a large location map linked back to the map with the listing selected; Future Property scenarios; price history as a step chart; MAKAN intelligence; a sticky contact card, and on phones a price-and-contact bar. |
| G5 | Smart search `/search/smart`                                          | B2     | **Verified** (preview) | R3: became the MAKAN Assistant (see A1). |
| G6 | Compare `/compare`                                                    | B2     | **Verified** (preview) | R3: properties as photo-led columns. "Only differences" by default; a magnitude bar and a "best here" mark on numeric rows, shown only when the values are comparable (same currency); a label column that stays put while columns scroll on phones; the labelled analysis. |
| G7 | Market intelligence `/market`                                         | B2     | **Verified** (preview) | R3: the reading (labelled AI) beside its facts (listings, period, demo share, confidence); asking-price range charts (P25–P75 bars with a median dot, one scale per purpose and currency) with the table one click away; areas ranked by median per m²; every statement with its kind and source; what cannot be measured yet; provenance. The CI market checks are unchanged. |
| G8  | Future Iraq `/future`                                                 | B2     | **Partial**  | Map preview and source cards exist. There is no classification and no map-led explorer (see F1–F3).                                                                                                                                                                   |
| G9  | Account, favourites, saved searches, notifications, messages          | B2     | **Partial**  | R1 gives every page the shared `PageHeader` and the new `EmptyState`. The account forms and message threads are not yet recomposed.                                                                                                                                   |
| G10 | Dashboard (agent): hub, listings, new listing, CRM, analytics, agency | B2     | **Partial** | R3: the hub is the agent's day. What needs action comes first (overdue follow-ups and tasks, new leads, unread messages, listings returned, drafts and expired), each linking to where it is handled. Then the listing status mix, recent listings and upcoming appointments. The CRM pipeline is restyled. Analytics and the listing form are not recomposed. |
| G11 | Admin: 13 pages                                                       | B2     | **Partial** | R3: the overview leads with what needs action (pending review, reports, errors, AI fallbacks); listings by status as one labelled bar; platform figures after. One data-table style across the admin and dashboard tables. The individual admin pages are not recomposed. |
| G12 | Auth: login, register, forgot, reset                                  | B1     | **Partial**  | The river map sits beside the form. Inputs are small and low contrast.                                                                                                                                                                                                |
| G13 | Pricing, status, credits, 404                                         | B1     | **Partial**  | Token-level only.                                                                                                                                                                                                                                                     |
| G14 | No horizontal overflow at 390 px                                      | B1     | **Verified** | After R1, 0 px overflow on all 144 captures, Studio and Vision at 390 px included.                                                                                                                                                                                    |

### 1.4 Map (signature experience)

| #   | Requirement                                                          | Source | Status       | Evidence or gap                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | -------------------------------------------------------------------- | ------ | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | Refined basemap styling and geographic context                       | B2, B4 | **Verified** | R2: MAKAN's own cartography (`lib/map/style.ts`) on the same free OpenMapTiles data replaces re-toning a third-party style. Two plates — Night chart and Limestone plate — with desert, palm groves, marsh, a lit river with its shoreline, a neutral road hierarchy, buildings from z14, labels in one language and no POI icons. Validated against the MapLibre style spec in unit tests; screenshots in both themes. |
| M2  | Camera eases on selection; controlled zoom and pitch; reduced motion | B2, B3 | **Verified** | Selection eases over 800 ms, zooms at most two levels and never rotates. The 20/20 draws and the selection screenshots confirm it. Reduced motion is coded but not yet checked by script.                                                                                                                                                                                                                               |
| M3  | Markers and clusters with selected and hover states                  | B2, B3 | **Verified** | R2: the price is the marker — limestone on the night chart, white on the light plate, emerald when selected. Balanced placement across a 150 px screen grid, with a quiet "+N" (direction-isolated, so it reads `+3` in Arabic) for nearby listings without room. Approximate locations are soft discs. Groups use the same material. Unit-tested placement.                                                            |
| M4  | Correct Arabic and English currency on prices                        | B3     | **Verified** | "269 مليون د.ع", "165 ألف دولار/شهر", "$165K/mo", all unit-tested.                                                                                                                                                                                                                                                                                                                                                      |
| M5 | Redesigned results list and mobile sheet                             | B2, B3 | **Verified** (preview, emulated touch) | R3: the results list is part of the map. A large live count; quick purpose and sort controls that change the URL; rows with photo, price, purpose, place, bedrooms and area; the same highlight as the map tag. Tablets get a docked rail. The phone sheet drag is tested with **emulated** touch (DevTools touch events) in the review run, not on a physical device. |
| M6  | Map, results, filters and selection stay in sync; URL sync           | B2, B3 | **Verified** | Viewport-to-URL sync, hover highlighting, "show on map" from the list, and drawing all verified (20/20).                                                                                                                                                                                                                                                                                                                |
| M7  | Layer controls with transitions                                      | B2     | **Partial**  | One panel with switches, and fades in code. The fades are not verified frame by frame.                                                                                                                                                                                                                                                                                                                                  |
| M8  | Drawing: entry, active and complete states                           | B2     | **Verified** | Screenshots of the active state; 20/20 draws.                                                                                                                                                                                                                                                                                                                                                                           |
| M9 | Transitions between map, preview and detail                          | B4     | **Verified** (preview) | R3: "View property" in the map preview morphs the photo into the property page's hero with a same-document View Transition. It falls back to a normal navigation where unsupported or under reduced motion; the link, new-tab use and history are unchanged. The property page's "Open on the map" returns to the map with that listing selected. |
| M10 | Real 3D only; name any extra data or credentials needed              | B2     | **Partial**  | OpenStreetMap footprints are extruded to OpenMapTiles heights. In Basra they are barely visible because few buildings are mapped. Terrain or photo-real 3D needs a paid provider (Mapbox, MapTiler or Google Photorealistic 3D Tiles) and an API key: **Blocked**.                                                                                                                                                      |
| M11 | Mobile performance safeguards                                        | B4     | **Partial**  | At most 140 tags, placed only when the camera stops. Not profiled on a mid-range device.                                                                                                                                                                                                                                                                                                                                |

### 1.5 Imagery and demo data

| #   | Requirement                                                      | Source | Status       | Evidence or gap                                                                                                                                                                                                                                                                                                                                                                                                           |
| --- | ---------------------------------------------------------------- | ------ | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I1  | Licensed real photos instead of generated drawings               | B3, B4 | **Verified** | 13 photos: 11 from Wikimedia Commons and 2 from Flickr via Openverse (CC0, CC BY, CC BY-SA), with licences checked at download and metadata removed.                                                                                                                                                                                                                                                                                                               |
| I2  | Clear "representative, not this property" labels and attribution | B3     | **Verified** | Card tag, gallery caption with author and licence, and the `/credits` page.                                                                                                                                                                                                                                                                                                                                               |
| I3 | Fix cropping, broken images, loading and layout shift            | B3, B4 | **Partial** | No broken images or layout shift. Library 11 → 13: Openverse works without a key within its anonymous limits (page size ≤ 20, paced). Two of 87 candidates were accepted after full-size review; the rest are shrines, people, press or non-Iraq photos. Home compositions show one listing per type first. Sourcing guide: `docs/DEMO-PHOTOS.md`. |
| I4  | Never imply demo listings or prices are real Iraqi market data   | B1, B4 | **Verified** | DEMO labels on cards, rows, the selection card, market figures and descriptions.                                                                                                                                                                                                                                                                                                                                          |

### 1.6 MAKAN AI and AI Property Studio

| #   | Requirement                                                                                                                                                                                                                            | Source | Status                                     | Evidence or gap                                                                                                                                                                                                                                                                                                                           |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1 | A first-class MAKAN AI assistant: natural-language search, property and neighbourhood Q&A, comparisons, budget and location refinement, market explanations, map-linked results, follow-ups, and entry points from details and the map | B2, B4 | **Verified** (UI)<br>**Demo only** (engine) | R3: the MAKAN Assistant (`/search/smart`). A multi-turn conversation in the URL; later details override earlier ones. Each reply shows what was understood, the matches on a map with price tags, links to map and list, a labelled market reading when asked, and refinements the reader understands. Every reply carries its provider label; with the default `mock` it says it is not a live model. Property Q&A stays on each property page (IntelligencePanel). |
| A2  | Real AI responses                                                                                                                                                                                                                      | B2, B4 | **Blocked**                                | Needs `AI_PROVIDER=claude` with `ANTHROPIC_API_KEY`, or `openai` with `OPENAI_API_KEY`, or `gemini` with `GEMINI_API_KEY`. The adapters exist and are unit-tested with mocked HTTP; none is configured.                                                                                                                                   |
| A3  | Studio A: visualise a plot or property (style, type, floors, camera, time of day)                                                                                                                                                      | B2, B4 | **Demo only**                              | `/vision` has a brief form with type, style, floors and plot. Output comes from the deterministic massing renderer (`mock`), labelled AI CONCEPT. There are no camera or time-of-day controls. Real images need `VISION_PROVIDER=openai` and `OPENAI_API_KEY` (**Blocked**).                                                              |
| A4 | Studio B: virtual drone flight (waypoints, altitude, preview, presets), kept distinct from AI video                                                                                                                                    | B2, B4 | **Verified** (preview) | R3: `/properties/<id>/flight`. A real MapLibre 3D camera over OpenStreetMap geometry: approach, orbit and rise presets; custom waypoints from your own views; altitude and duration; recording with MediaRecorder from the map canvas, then download. Labelled as not AI video and not photographic. Linked from the property page. |
| A5 | Studio C: construction-stage timeline, labelled illustrative                                                                                                                                                                           | B2, B4 | **Demo only** (illustrative) | R3: the construction sequence on the same page: a massing block sized from the listing's area and floors rises through site, foundations, structure, envelope and complete on the real map, recordable. Labelled as illustrative massing, not a design and not AI video. AI-generated construction video is **Blocked**: no video provider. |
| A6  | Studio D: media jobs with states, progress, retry and export                                                                                                                                                                           | B2, B4 | **Partial**                                | `/studio` has job states and a browser-rendered video made from listing photos with MediaRecorder: a real video, but not AI. No unified job view across Studio and Vision. External renderers: **Blocked**.                                                                                                                               |

### 1.7 Future Property and Future Iraq

| #   | Requirement                                                                                                                                                                | Source | Status      | Evidence or gap                                                                                                                                                                                                                               |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1 | Future Iraq classification: strategic / investment / priority development, with definitions, treatments, map filters and detail panels                                     | B2, B4 | **Missing** (needs a migration — proposal below) | No classification is shown, because none exists in the data. The proposed migration is set out in §4; it is not run. |
| F2  | Evidence, sources, rationale and missing information per project                                                                                                           | B2, B4 | **Partial** | Sources, dates, confidence and location precision are shown. There is no classification rationale or list of missing fields.                                                                                                                  |
| F3  | Smallest safe data-model change                                                                                                                                            | B2     | **Missing** | Proposed: `programme_class` (`STRATEGIC`, `INVESTMENT`, `PRIORITY`, `UNCLASSIFIED`; default `UNCLASSIFIED`), `programme_basis` (text), and `programme_source_id` (an FK to an existing source). One migration and no change to existing rows. |
| F4 | Future Property: existing vs proposed, scenarios, phases, alternatives, context and constraints, with facts, assumptions, concepts, projections and unknowns kept separate | B2, B4 | **Partial** | R3: Future Property scenarios on property pages for land, houses, villas and farms with a known area. Facts (plot, floors), assumptions you set (coverage, floors, apartment size, your own build cost), and a projection (floor area, apartments, build cost, an indicative sales value from the market report's apartment median, labelled with its sample and demo status). Links to the massing. Neighbourhood and investment scenarios beyond the existing investment analysis are not built. |

### 1.8 Existing functionality (must not regress)

| #   | Flow                                                                                                             | Status       | Evidence                                                                                                                      |
| --- | ---------------------------------------------------------------------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| E1  | Sign-in and roles (agent, admin)                                                                                 | **Verified** | The screenshot script signs in as agent and as admin and opens 27 protected pages, each returning 200 with no console errors. |
| E2  | Listing search, filters, pagination, sort                                                                        | **Partial**  | Pages load. Filter interactions are not exercised by the script; CI has unit tests.                                           |
| E3  | Map search, drawing, near me, places, Future Iraq layer                                                          | **Verified** | MapLibre check plus the live browser check script. "Near me" is covered in CI by `browser_check`.                             |
| E4  | Favourites, saved searches, notifications, messages                                                              | **Partial**  | Pages load as the agent. Saving and messaging are not re-tested in the browser.                                               |
| E5  | Compare                                                                                                          | **Partial**  | Empty state loads. A two-listing comparison is not captured.                                                                  |
| E6  | Dashboard listings, new listing form, CRM, analytics, agency                                                     | **Partial**  | All load. The new-listing submit is not re-tested in the browser (backend tests cover it).                                    |
| E7  | Admin: users, moderation, verification, AI, analytics, reports, billing, jobs, audit, system, settings, webhooks | **Partial**  | All load. Billing and settings show the hub for this demo admin (role permissions), which is expected.                        |

---

## 2. Why the interface still looks cheap

Each finding comes from the audit captures. Ten reasons, in order of damage.

### 2.1 It matches the generated-design look

A near-black canvas, one acid emerald accent, hairline rules between everything, and middle-dot meta strings ("بيت · العشار، البصرة"). This is the most common signature of generated pages. The rules make every section look like the same spreadsheet. Pass 1 removed boxes but replaced them with _more lines_, not with composition.

### 2.2 Typography has no voice and is too small

- **Too small.** At 1440 px most text is 12–13 px grey (`text-xs`, `caption`, `meta`): about 150 occurrences of `text-xs` alone. Prices, the most important data, are set at 15–19 px.
- **Too heavy where it is large.** Arabic display is Readex Pro at weight 600 with a heavy black colour; it shouts, then everything below it whispers.
- **No optical sizing.** Latin headings use Inter's text cut at 80 px, which is loose and generic. Inter's display optical size, and Readex Pro's HEXP width axis, are not loaded.
- **Low contrast.** Secondary ink `#A7ADB4` on `#0A0C0F` is fine, but tertiary `#737A83` is used for content (place names, areas), not only for metadata.

### 2.3 Composition repeats and empties the page

- **Home:** every section is the same "title column + ruled content" block, four times.
- **Other pages** (compare, favourites, saved searches, notifications, messages, account, status, studio, vision, smart search): a small block in the middle of a 1440 px dark void, then a 300 px footer. Large empty areas carry no information. "Minimal" became "unfinished".

### 2.4 The map, MAKAN's signature, is presented like a utility

- **Home hero:** green dots on an almost black street mesh, with no prices, water barely visible and no sense of place. It reads as a debug view.
- **Map page:** the dark basemap is flat. The rail is a plain dark column.

### 2.5 Imagery is weak and repetitive

Hazy, inconsistent photos repeat in a 3-up grid. Every card has the same crop, colour cast varies, and there is no treatment unifying the set.

### 2.6 Components feel default

- **Sizes:** buttons are 32–40 px with 13–14 px labels. Inputs are 44 px with a barely visible fill.
- **Native controls:** checkboxes, `<select>` and the file input ("No file chosen") are browser defaults.
- **Hand-rolled actions:** CRM's "new lead" is a full-width green bar, and links are styled as buttons by hand in dozens of places.

### 2.7 Dashboards and admin are generic tiles

The overview and analytics pages are grids of identical boxes with a tiny label and a "0". Hubs are lists of identical link rows. There is no hierarchy between what matters (pending moderation, new leads) and what doesn't.

### 2.8 Pages are inconsistent with each other

Property detail, smart search, market, Studio and Vision still use the old styling: boxed panels, different title sizes (`text-4xl` vs `display-md` vs `display-lg`), different widths (`max-w-xl` … `max-w-7xl`). It does not feel like one product.

### 2.9 States are tiny

Empty, loading and unavailable states are 14 px text in a box. The Studio preview is a large blank white rectangle, and Vision's preview is a dashed outline.

### 2.10 Motion is either absent or generic

The map has purposeful motion. Elsewhere, motion is fade-up-on-load (`reveal`) or nothing. There are no transitions between list, preview and detail, and there is no considered page-level moment.

---

## 3. Recovery plan

Each pass ends with a preview and screenshots for review. Visual polish and functional work are reported separately.

### Pass R1 — art direction, typography, components, shell (this checkpoint)

**Direction: "Night over the Shatt" (ليل على شطّ العرب).**

| Area        | Direction                                                                                                                                                                                                                                                                                                                  |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Base colour | The agreed brand navy, not graphite: `#0B0F17` canvas and `#161E2E` raised surfaces, with derived steps.                                                                                                                                                                                                                   |
| Ink         | A warm limestone white (`#F2EEE7`) instead of cold grey. The warmth of Basra brick and limestone against the blue night is MAKAN's material contrast, rather than another accent colour.                                                                                                                                   |
| Accents     | Emerald `#10B981` is for action only (one fill per view). River cyan `#06B6D4` is for place. Date-palm gold is for uncertainty (DEMO, estimates, concepts).                                                                                                                                                                |
| Light theme | A cool limestone canvas with the brand navy as ink: the same identity, inverted.                                                                                                                                                                                                                                           |
| Type        | Load Inter's optical sizes (display cuts at large sizes) and Readex Pro's full axes. Arabic display at weight 500, not 600, with more leading; Latin display tighter. Raise the floor: body 16/17 px, metadata 14 px, captions 13 px only for credits and footnotes. Prices are a typographic event (Inter, tabular, 600). |
| Structure   | Fewer rules. Group with space and with one surface step. Page headers, panels and data rows replace ad-hoc boxes and lines. No middle-dot meta strings; use separate, aligned values with icons where useful.                                                                                                              |
| Components  | 44 px controls (36 compact, 52 large), 10 px control radius, 16 px panel radius, 24 px sheet radius. Styled checkbox, select and file inputs. One `PageHeader`. A larger, purposeful `EmptyState`. A `Metric` row for dashboards.                                                                                          |
| Shell       | A taller header with the wordmark, larger navigation and a clear active state. A compact footer instead of a 300 px block. Page widths from one scale.                                                                                                                                                                     |
| Home        | A full-bleed map hero of real Basra geography with live price tags, revealed by one orchestrated camera move (instant under reduced motion). A photo-led Basra section, market figures as a band, and the river map returning as the city index.                                                                           |

#### R1 outcome (what the preview shows)

**Visual (polish):**

- Palette, ink and type scale as above.
- Shared `PageHeader` on 28 pages and the new `EmptyState` on 6.
- One button and field system.
- Rebuilt header and footer.
- New home composition.
- A price-led `PropertyCard`.

**Functional:** none added in R1. The only behaviour changes are layout fixes:

- Studio and Vision no longer overflow on phones.
- The phone theme control moved into the menu.

**Not done in R1, by design:**

- Property detail, the compare table and market charts (R3).
- The assistant and Studio tools (R4).
- Classification and dashboards (R5).

### Pass R2 — map signature (this checkpoint)

**Diagnosis before redesign.** The previous map was a third-party style re-toned to graphite: near-black, flat, with labels in two scripts and hollow cyan rings that read as debug points; the price pills floated away from their spots. The home hero showed no prices for 2.4 s after the map appeared — reproduced in a real browser with a timeline (`hero_timeline` in the review run): ready at 3.3–4.3 s, first price at 5.8–6.6 s, so the review run captured none (light) or a few (dark). The cause was placement after a 2.4 s camera move, plus a greedy pass that gave 13 of 48 listings a tag.

**Direction.**

- **Plates, not a recolour.** Night chart (navy land, lit river, palm groves, marsh, limestone labels) and Limestone plate (warm paper, blue water with a drawn shore, sand highways). Both come from the same free tiles.
- **The price is the marker.** Light tags on the dark map and white tags on the light one. Emerald means selected. Spread over the view; "+N" means "more here".
- **Restrained motion.** The hero arrival is one 1.8 s move, with prices rising in from 35 % of it. Selection opens a ground halo, lifts the tag and raises the preview. The camera moves only when it must, and everything is instant under reduced motion.

**Genuine vs. limited.**

- **Genuine:** all of the above runs in MapLibre on real OpenStreetMap data. 3D shows real footprints extruded to OSM heights.
- **Limited:** Basra has few mapped buildings, so 3D and the building fill are sparse. There is no terrain and no photo-real 3D: those need a keyed provider. Street names and districts are only as complete as OSM.

### Later passes, for approval one at a time

- **R3 — property detail, imagery, smart search, compare, market:** photo library expansion through Openverse, a new detail composition, insight panels, a comparison table, market charts from real medians.
- **R4 — MAKAN AI and Studio:** an assistant over the existing grounded endpoints, clearly showing the mock vs live provider. A MapLibre camera-path "drone" tool (real 3D camera, no AI), illustrative construction stages, and one job tray.
- **R5 — Future Property, Future Iraq classification, dashboards, admin:** the `programme_class` migration (§1.7 F3), a map-led project explorer, scenario framework, and metric-led dashboards.
- **R6 — full regression and visual QA:** tablet widths, keyboard focus and reduced-motion scripts, light theme everywhere.

### External providers still required

| Capability                          | Needed                                                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Live MAKAN AI answers               | One LLM provider key: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` (set `AI_PROVIDER`).          |
| Real image generation (Vision)      | `VISION_PROVIDER=openai` and `OPENAI_API_KEY` (or a new adapter for another provider).                        |
| AI video generation                 | Not implemented; needs a provider such as Runway or Luma, plus an adapter and a job worker.                   |
| Photo-real 3D and terrain           | Mapbox, MapTiler or Google Map Tiles API key and terms review.                                                |
| More licensed property photography  | Openverse (no key, rate-limited), or a stock licence, or photos supplied by the owner.                        |
| Official Future Iraq classification | An authoritative source per project (ministry plan, NIC list). Without one, a project stays **Unclassified**. |

## 4. Future Iraq classification — proposed migration (not run)

**Why a migration is needed.** The brief asks for strategic / investment / priority development classes with evidence. Projects today have `category` (port, road, housing…) and `status`, and nothing else records a programme class or why. Inferring a class in the frontend would present a guess as an official status, which the brief forbids. So the class has to be stored, with the evidence that justifies it.

**Smallest safe change.** One Alembic migration on `development_projects`, with no change to existing rows:

| Column | Type | Default | Meaning |
| --- | --- | --- | --- |
| `programme_class` | enum `STRATEGIC`, `INVESTMENT`, `PRIORITY`, `UNCLASSIFIED` | `UNCLASSIFIED` | The class, only when a source says so. |
| `programme_basis` | text, nullable | null | One sentence: why this class (quoting the source). |
| `programme_source_id` | FK → `development_sources`, nullable | null | The document that states it. |

**Constraint.** `programme_class <> 'UNCLASSIFIED'` requires `programme_source_id` (a check constraint), so a class can never exist without its evidence.

**After the migration:**
- **API:** the projects endpoint returns the three fields.
- **Admin:** editors can set them, and the change is audited.
- **`/future` and the map layer:** a filter by class, a legend, and a panel per project saying the class, the basis and the source — or "Unclassified: no official classification found".
- **Seed data:** only the two National Investment Commission opportunities can honestly be set to `INVESTMENT`, citing their NIC listing. Everything else stays `UNCLASSIFIED`.

**Not done until approved.**
