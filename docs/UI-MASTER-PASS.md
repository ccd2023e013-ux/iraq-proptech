# MAKAN visual master pass (branch `ui-master-pass`)

**Status: UNVERIFIED. Not merged. Frontend only.**

The project's own tools have not been run on this branch, because this environment cannot reach the npm registry and GitHub Actions is paused (see "What was and was not verified"). Do not merge until CI, the browser checks and a human review on a preview have passed.

No backend, API contract, database, authentication, Render, Supabase, scheduled-job or deployment file was changed. No Stage 8 code is included.

## Design system (`src/app/globals.css`)

**Colours.**
- Foundation `#0B0F17` and surface `#161E2E` (dark default); light canvas `#F8FAFC`.
- Emerald `#10B981` means action, confirmed or selected. Cyan `#06B6D4` is used only for spatial things: map, places, location, layers.
- Date-palm gold marks DEMO and estimate signals.

**Depth model.** One vocabulary, used everywhere:

| Layer | Class | Look |
| --- | --- | --- |
| canvas | `body` | the page background, with one faint light from above |
| surface | `.surface-1` | solid, with a hairline highlight on the top edge and a soft shadow |
| float | `.surface-float` | translucent with 20px blur, for panels above content or the map |
| focus | `.surface-focus` | raised solid with a deeper shadow, for the selection, popovers and menus |
| modal | `.surface-modal` | strongest translucency with 28px blur, for sheets and dialogs |

Tokens: `--surface-raised`, `--float-bg`, `--float-bg-strong`, `--float-ring`, `--edge`, `--scrim`, `--shadow-focus`, `--shadow-modal`, `--canvas-glow`, `--grid-line` (light and dark); `--blur-float`, `--blur-modal`. Without backdrop-filter support, float and modal surfaces become solid.

**Type.** Readex Pro for Arabic, Inter for Latin and numerals. Classes:
- `.display-xl`, `.display-lg`, `.display-md`: fluid sizes, tight Latin tracking, taller Arabic line height;
- `.meta` for compact metadata;
- `.kpi` for large tabular numbers;
- balanced headings and pretty paragraphs.

**Layout constants.** `--header-h` (4rem on phones, 4.25rem for the floating bar), `--tabbar-h` (phones only), and a z-index scale: `--z-float`, `--z-header`, `--z-tabbar`, `--z-sheet`, `--z-modal`, `--z-toast`.

**Components (CSS).**
- `.chip` (selected = emerald) and `.chip-spatial` (selected = cyan);
- `.seg` segmented control (aria-pressed, aria-checked or aria-selected);
- `.field`, `.icon-btn`, `.press` (physical compression), `.lift` (hover elevation);
- `.stage-grid` (a faint survey grid fading out from the centre), `.skeleton`, `.quiet-scroll`.

**Icons.** `components/ui/Icon.tsx` is one family: 24-unit grid, 1.75 stroke, round caps. It has about 40 glyphs, including search, map, layers, pin, locate, draw, insight (analysis frame, not a robot), market, future, heart, filter, bed, bath, area, and arrows that mirror in RTL. Header, tab bar, map tools, cards, gallery, states and the property page use it.

## Motion

Durations are `quick` 140ms, `base` 240ms, `spatial` 420ms and `slow` 560ms. `--ease-spring` is a soft physical spring (CSS `linear()`, with a cubic-bezier fallback). Only transform and opacity are animated.

**Animation classes.**
- `.reveal`: rise with a stagger index (`lib/motion.ts` `stagger(i)`, 45ms steps, capped at 8);
- `.pop-in`: arrival in space;
- `.sheet-in`: bottom sheet;
- `.fade-in`;
- `.icon-swap`: the theme glyph turns in;
- heart pop on save (only when the user saves);
- Basra pulse (twice, then rests);
- skeleton light sweep.

**Where motion is used.**
- Page enter (existing template).
- Header and tab-bar active states, with a spring lift on the active tab.
- Buttons and chips compress when pressed.
- Cards lift, and their image drifts slowly on hover.
- Menus and popovers pop in.
- The map selection card replays its arrival when a different listing is chosen.
- The map camera eases to the chosen listing, offset to the open part of the map.
- The gallery cross-fades between photos.
- Results lists reveal in a stagger.
- Key numbers count up once when they scroll into view (`AnimatedNumber`, server-rendered final value).

`prefers-reduced-motion` removes every animation, delay and transition. The pulse is hidden, and numbers render static.

## Screens

**Shell.**
- A floating header bar from md up, inset and translucent over content, with an active-page pill (`PrimaryNav`).
- A slim bar on phones, plus a floating native-style tab bar (`MobileTabBar`): Home, Map, Properties, Future, Saved or Sign in.
- Menus and the user menu use focus surfaces. The compare bar sits above the tab bar.
- The footer carries the brand mark.

**Map (`/map`).** Full-bleed and map-first.
- On wide screens the stage runs under the floating header.
- A results rail floats on the start side (≥1024px). On phones and tablets it becomes a bottom sheet with a handle; it closes while a listing is selected.
- Map tools float on the end side as glass buttons: layers, draw, near me.
- Zoom sits at the bottom of the end side. MapLibre controls are restyled as floating surfaces.
- The selection card is centred in the open map area.
- Drawing hints and errors are shown as floating status pills.
- Loading shows a skeleton stage.
- Every test id and accessible name used by the live checks is kept (`map-total`, `map-layers`, `draw-area`, `finish-area`, `map-selection`, `map-project`, `data-place`, `data-layer`, "Near me").

**Home.**
- The hero is a spatial stage: survey grid, the river map as the ground, the floating search, the brand descriptor and a link to Basra on the map. It runs under the floating header.
- Section headings use the display scale.
- Market KPIs are large numbers that count up.
- Surfaces follow the depth model.

**Property cards.**
- Editorial: the photograph carries the card, which lifts with a slow image drift on hover.
- Chips sit on a soft top shade; DEMO stays gold.
- The price leads. The location has a cyan pin, and the facts show bed, bath and area icons, with screen-reader labels.
- Compare appears on hover (always on touch).

**Property page.**
- Immersive gallery (21:9 on wide screens, glass controls, arrow keys that respect RTL, a lifted current thumbnail).
- Display title, pinned location, KPI stats with icons.
- Facts use progressive disclosure: six facts first, the rest behind "Show all details".
- Amenities have check marks. The price panel is a focus surface.
- The AI Vision link is an analysis card.

**AI.**
- The intelligence panel: an analysis-frame icon, a thin rail in each statement's kind colour, and a small confidence meter.
- A skeleton while analysing.
- No robot or brain imagery.

**Future Iraq.**
- An urban-intelligence header: survey grid, real counts by status (counting up), and the projects plotted from their recorded coordinates (numbered, matched to the list).
- A timeline spine with status nodes.
- Sources sit behind disclosure (the first project is open).
- "Show on map" uses cyan.

**States.**
- `EmptyState`: a quiet glyph on the survey grid, with an action.
- Calm error page: retry and home, with the digest reference only.
- 404 with a spatial glyph.
- Alerts with tone icons.

**Listings (`/properties`).** Surfaces, chips for "Smart search" and "Map", the designed empty state, staggered results and pill pagination.

**Market Intelligence page.** Not changed. It exists only on the frozen Stage 8 branch.

## What was and was not verified

**Done in this environment.**
- **Static review** of every changed file.
- **Prettier:** all files pass.
- **TypeScript (strict, `noUncheckedIndexedAccess`):** the whole `src` passed, checked against React 19 type definitions with Next.js and MapLibre stubbed. The only remaining errors come from the MapLibre stub's `any` types in untouched code.
- **Visual proof:** pages were rendered to static HTML with a minimal React runtime and the real page components. They used synthetic proof data (local only, never committed) and the real Future Iraq dataset. The CSS was compiled with the Tailwind v4 standalone CLI and screenshotted in Chromium.
  - Covered: home, map, property, listing, Future Iraq and 404, in Arabic and English, dark and light, at 1920, 1440 and 390 widths.
  - No horizontal overflow was found in the captured views.
  - The proof cannot run JavaScript, the MapLibre map, data fetching or animation.

**Not done: must run when tooling returns.**
- ESLint.
- Vitest (existing component tests).
- `next build`.
- The real browser in the live checks: the market matrix and the existing map, auth and property journeys. Pay special attention to the map stage: the drawing clicks around the canvas centre, `map-total` visibility, the first `/properties/` link in the rail, and "Near me".
- Real map rendering beneath the floating panels.
- Readex Pro rendering (the proof used a fallback Arabic font).
- Motion feel on real devices.
- iOS safe-area handling for the tab bar.
- Keyboard navigation end to end.

**Expected merge conflicts with `stage-8-market`:** `src/app/page.tsx` (market section badge), `src/components/ui/TrustBadge.tsx`, `src/i18n/dictionaries/*`, and `scripts/live/browser_check.py` is unaffected. Resolve them after Stage 8 is complete.

---

# Premium redesign pass (branch `design/premium-redesign`)

This branch merges the latest work and then verifies and extends the master pass in a real browser:
- `stage-8-market`;
- `deps/next-16`, which brings Next 16, MapLibre 6 and the issue #4 fixes;
- `security/public-release`;
- `ui-master-pass`.

Every change below was reviewed on screenshots of the running app. The screenshots cover Arabic RTL and English LTR, dark and light themes, and 1920, 1440 and 390 px widths. They are pushed by the preview workflow to `screenshots/design-<run>` branches.

## Cartography (`lib/map/basemap.ts`)

The basemap is context and MAKAN's data is the figure. This follows the usual map-design hierarchy (Mapbox map-design process).

When the provider is OpenFreeMap, the style is re-toned on load:

| Element | Dark | Light |
| --- | --- | --- |
| Land | `#0d121c` (≈ canvas) | `#f4f6f9` |
| Water | `#0a2230` (low-chroma cyan) | `#cce5ee` |
| Roads | step up in lightness by class; casings melt into the land | white on soft land |
| Labels | muted slate (`#7c879c`), places brighter (`#a3aec2`), canvas halo | slate, white halo |

The function is pure and unit-tested (`basemap.test.ts`). A layer that lacks a paint property is left as designed.

## Markers

- **Price tags** are small raised surfaces (surface colour, hairline edge, ink text). Each sits just above an emerald dot marking the exact spot. The dot stays visible when tags collide.
- **Selection** is emerald with dark text (contrast).
- **Groups** are cyan discs with a soft halo and dark count text (8:1 on cyan).

## MapPreview (`features/map/MapPreview.tsx`)

MapPreview is a quiet, non-interactive map for places that matter but don't need exploring:
- the listing location;
- the Future Iraq header.

How a position is drawn:
- **Exact positions:** pin-head dots, numbered when keyed to a list.
- **Approximate or area positions:** a soft disc, with only the key number and never a site dot.
- **Hidden locations:** no preview.

The real basemap replaces the abstract dot plot on `/future`.

## Layout and components

- `/map` is a full-screen app surface: no footer (`HideOnRoutes`), and no page scroll.
- **Listings without photos:**
  - the listing page shows a slim band, so the facts lead;
  - cards, the map rail and the selection card show a designed placeholder glyph.
- **DEMO badges:** dark text on gold (6.9:1). White on gold was 2.9:1.
- **Header:** favourites and saved searches moved to the account menu on wide screens, and stay in the phone menu.
- **Admin:** a `SectionNav` with a current-page marker on wide screens, and a chip row on phones.
- **Dashboard:** quick links are icon tiles.
- **Smart search:** an intro, one search surface and example queries. "Understood" chips no longer use arrows, which pointed the wrong way in RTL.
- **Compare:** the empty state invites the next step.
- **Market:** P25–P75 range bars with a median tick on a shared scale per purpose and currency. The values come from the report, and the text is unchanged.
- **Digits:** Latin everywhere (`ar-IQ-u-nu-latn`). Nearby distances were Arabic-Indic.

## Preview (`.github/workflows/design-preview.yml`)

Every push to the branch:
1. builds the same Docker stack as CI on a standard runner, seeds DEMO data, and exposes only the web app through a Cloudflare quick tunnel;
2. publishes the URL as the commit status `design-preview`;
3. takes the design screenshots, runs the MapLibre browser check, and pushes both to a `screenshots/design-*` branch.

Isolation:
- no repository secrets are used;
- JWT, database and demo passwords are generated per run;
- production is never contacted.

Demo passwords are published only encrypted to the reviewer's key. A preview lives up to about 5½ hours. Re-run the job for a new one.
