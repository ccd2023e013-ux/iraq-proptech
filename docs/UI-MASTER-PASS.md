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
