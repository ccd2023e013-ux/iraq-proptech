# MAKAN visual direction: "The Survey" (المسح)

This document sets MAKAN's art direction. Every screen, component and motion follows it. It replaces the earlier "glass pills on navy" look, but the product's architecture and behaviour are unchanged.

## 1. Personality

MAKAN reads the city the way a surveyor reads a site: precisely, calmly, and from the ground up. Its users are in Iraq, so the product is designed in Arabic first.

- **It is:** exact, quiet, confident, local and honest about its data.
- **It is not:** glossy, futuristic, playful, neon, or "AI-styled".

**The one bold thing.** MAKAN's identity rests on the **map and the measured number**. Each screen spends its contrast on one figure: a map, a photograph, a price, or a large figure. Everything else steps back.

## 2. Principles

1. **Structure through alignment and rules, not boxes.**
   - Content sits on the page, and hairline rules divide it.
   - Panels exist only where something is genuinely layered: over the map, over imagery, in a dialog.
   - No grids of identical rounded cards.
2. **Asymmetric, editorial composition.**
   - A strong start column (titles, the key number) faces a wide end column (the map, imagery or list).
   - In Arabic the start column is on the right. Compositions are drawn from the right edge, and LTR is their mirror, not their origin.
3. **Truth is visible.** Fact, observed, estimate, AI output, user assumption, demo and unavailable each have one fixed treatment (the trust badges). Colour never implies certainty.
4. **Motion explains change.** Movement shows where something came from, where it went, or what changed. Nothing moves to look alive.
5. **Density with air.** The spacing is tight and precise inside a group and generous between groups. Empty space separates; it never stands in for content.

## 3. Colour

The base is neutral graphite and limestone, not navy. The neutrals have a hint of warmth, like stone and concrete, which reads as architecture rather than "tech blue".

### Dark (default): basalt

| Token | Hex | Use |
| --- | --- | --- |
| `--canvas` | `#0A0C0F` | page ground, map surround |
| `--surface` | `#111418` | content resting on the ground |
| `--surface-raised` | `#181C21` | raised panels, menus |
| `--fill` | `#1D2127` | control fills, quiet tiles |
| `--fill-strong` | `#262B32` | pressed or selected fills |
| `--hairline` | `rgb(214 220 226 / 0.09)` | rules |
| `--hairline-strong` | `rgb(214 220 226 / 0.16)` | control outlines |
| `--ink` | `#EDEEEF` | primary text |
| `--ink-2` | `#A7ADB4` | secondary text |
| `--ink-3` | `#737A83` | tertiary text, captions |
| `--accent` / `--accent-fill` | `#34D39E` / `#14B07F` | action, confirmed, selected (emerald) |
| `--spatial` / `--spatial-fill` | `#4CD3E6` / `#14B4CC` | maps, places, layers, location (cyan) |
| `--gold` / `--gold-fill` | `#DDB15E` / `#C49640` | DEMO, estimates, projections (date-palm gold) |
| `--positive` / `--caution` / `--critical` | `#3FCF95` / `#E8AC45` / `#F27A6E` | status |

### Light: limestone

The ground is cool stone `#F2F3F1`, not cream. Surfaces are `#FFFFFF`, ink is `#0E1114`, secondary ink is `#4B525A`, emerald is `#0B8C63` and cyan is `#0A7C96`.

### Rules

- **Emerald** is for *doing*: the primary action, selected states and confirmations. Use it at most once as a fill per view.
- **Cyan** is for *where*: maps, layers, locations and places. It never marks an action.
- **Gold** is for *uncertain or illustrative*: DEMO, estimates and generated concepts.
- **Status colours** appear only with an icon or text, never as colour alone.

## 4. Typography

**Faces.**
- Arabic: Readex Pro.
- Latin and all numerals: Inter.
- Self-hosted, with tabular figures for numbers.

**Display.** Arabic display type runs about 10% larger than Latin, at weight 600, with a 1.25 line height and no tracking. Latin display uses weight 600, a 1.04 line height and −0.025em tracking.

**Scale.** Fluid, about a 1.25 ratio.

| Class | Size | Use |
| --- | --- | --- |
| `.display-xl` | 44–80px | hero |
| `.display-lg` | 34–52px | page titles |
| `.display-md` | 26–34px | section titles |
| `.title` | 20px | panel titles |
| body | 16px; Arabic 17px with 1.85 leading, Latin 1.6 | |
| `.meta` | 13px | metadata |
| `.caption` | 12px | captions |

**Treatments.**
- **Labels:** sentence case, never all caps, and no eyebrow labels above headings.
- **Large figures (`.kpi`):** Inter, weight 600 and tabular, with the unit set smaller in the secondary ink.

## 5. Grid and spacing

**Grid.**
- **Desktop:** 12 columns, 1320px maximum width, 24px gutters, and 48px margins at 1440px and above.
- **Tablet:** 8 columns.
- **Phone:** 4 columns with 16px margins.

**Spacing.** Every spacing value comes from a 4px scale: 4, 8, 12, 16, 24, 32, 48, 64, 96 and 128. Inside a group use 8–16px; between groups use 48–96px.

## 6. Shape

| Radius | Value | Use |
| --- | --- | --- |
| `--radius-tag` | 3px | trust badges and status tags |
| `--radius-control` | 6px | buttons, fields, chips, segmented controls |
| `--radius-card` | 10px | panels, media, the selection card |
| `--radius-sheet` | 16px | bottom sheets (top corners only) |

- **Round only where the object is round:** avatars, dots, switches.
- **No pills for buttons.**

## 7. Surfaces, depth and light

Depth comes from **luminance steps**: canvas, then surface, then raised, then overlay. Shadows do not create depth on the page.

- **Hairline rules** separate content on the page.
- **Overlays** are the only elements with blur and a shadow: map controls, sheets, menus and dialogs. Overlays on the map use 72% opacity with a 16px blur.
- **Light.** Raised elements in dark mode get one 1px top highlight (`--edge`). There are no gradients except under imagery, where a gradient keeps the text legible.

## 8. Iconography

- **One family** (`components/ui/Icon.tsx`): a 24-unit grid, round joins, a 1.6 stroke at 20px and above and a 1.8 stroke at 16px.
- **Optical alignment:** icons sit on the text's x-height centre.
- **Directional glyphs** (arrow, chevron, back) mirror in RTL.
- **Active states** combine the accent colour with a 2px indicator bar beside or under the item. Icons never carry meaning alone.

## 9. Buttons

| Kind | Look | Use |
| --- | --- | --- |
| primary | emerald fill, near-black text | one per view: the main forward action |
| secondary | hairline outline, ink text | alternatives |
| tertiary | text only; underline on hover | low-emphasis actions |
| destructive | critical outline; fills on hover | irreversible actions |
| icon | square, 40px (36px compact) | tools |

Heights are 32, 40 and 48px. Every button has designed states:
- **Hover:** a luminance step.
- **Press:** translateY(1px) plus a darker fill (80ms).
- **Focus:** a 2px emerald ring with a 2px offset.
- **Loading:** a spinner replaces the icon and the width stays fixed.
- **Disabled:** 40% opacity and no hover.
- **Success:** the label briefly changes to a check, and the fill stays put.

## 10. Motion

### Tokens

| Token | Duration | Use |
| --- | --- | --- |
| `--dur-instant` | 80ms | press |
| `--dur-quick` | 140ms | hover, colour |
| `--dur-base` | 220ms | state changes, menus |
| `--dur-panel` | 360ms | panels, sheets, page content |
| `--dur-camera` | 700–1100ms | map camera |

### Easing

| Token | Curve | Use |
| --- | --- | --- |
| `--ease-standard` | `cubic-bezier(.2,0,0,1)` | most changes |
| `--ease-exit` | `cubic-bezier(.4,0,1,1)` | exits |
| `--ease-spring` | a soft settle with no bounce | sheets |

### Distance

- 4px for micro movement.
- 8px for content entering.
- 24px for panels.
- Full height for sheets.

### Rules

- Animate transform and opacity only.
- Never block input.
- Stagger at most one group per screen.
- Under reduced motion, movement becomes a crossfade or an instant change.

## 11. Map and camera (detailed in Pass 2)

- **The basemap is context.** It is re-toned to the palette, quiet, with water as the only colour.
- **Camera moves are eases, not flights:**
  - Selecting a listing eases to it in 700–900ms. Zoom changes by at most 2 levels, and the camera offsets so the listing clears the open panel.
  - Bearing never changes unless the user rotates.
  - Pitch is used only where real 3D data exists. OpenFreeMap building heights allow honest extrusions; there is no fake 3D.
- **Markers:**
  - Price tags are small raised surfaces; the selected tag grows slightly and turns emerald.
  - Clusters expand with a camera ease to their bounds.
- **Drawing has three visible states:** entry (hint), active (vertices and a live outline) and complete (the area settles into a cyan outline).

## 12. Composition per page (Pass 1 scope in bold)

- **Shell:**
  - The header is a full-width bar with a hairline base, the wordmark at the start and text navigation with an underline indicator.
  - Phones get a flat tab bar fixed to the bottom edge.
  - The footer is an editorial index.
- **Home:**
  - The hero pairs the Arabic headline (start column) with a live, quiet map of Basra's listings (end column), with search beneath the headline.
  - Then come ruled sections in a start-title/end-content layout: Basra listings, the market reading, the city index and what is coming next.
- **Property cards:** an image (10px radius), then the price as the figure, then the title, place and facts as a single quiet line. DEMO is a gold tag on the image's bottom edge, and nothing else floats on the image except the save control.
- **Listings:**
  - Filters form a ruled column on desktop and a single button with a sheet on phones.
  - Results sit in a 3-column grid with ruled row separators.
- Map, AI, Studio and Future Iraq follow in Passes 2–4, using the same tokens.
