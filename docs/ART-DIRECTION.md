# MAKAN art direction — "The survey plate"

This replaces the visual sections of `docs/DESIGN-DIRECTION.md` where they
conflict. It records why the previous passes still looked ordinary, the concept
that replaces them, and the rules the code follows.

## Why the interface still felt inexpensive (October 2026 audit)

Reviewed on the preview at 1440, 768 and 390 px, Arabic and English, light and dark.

1. **A landing-page hero over a map.** A marketing headline ("Property
   intelligence that understands place") and a form card sit on a map that is
   washed out under a gradient. The map is wallpaper; the first screen answers
   none of "where am I, what is here, what matters, what next".
2. **Default typography.** Inter for English and Readex Pro for Arabic, set in
   the bold-and-tight SaaS display style. Nothing about the type says Iraq,
   place or property; Arabic and English look like two different products.
3. **Template marketplace parts.** The same rounded photo card everywhere, a
   filter sidebar of chips, "Basra first / Market reading / Explore by city"
   sections each in its own rounded box.
4. **Repetition.** Thirteen licensed photos serve 156 demo listings, so one
   page shows the same street three times. Repetition reads as fake.
5. **Label noise.** A listing card carried up to three gold badges (Demo,
   representative photo, promoted) plus a type chip; trust was shouted, not stated.
6. **Price markers as notifications.** White chips with "+5" bubbles: they read
   as unread counts, not as prices on land.
7. **Everything is a card.** Equal radii, equal hairlines and equal shadows on
   every object flatten the hierarchy.

## Concept

A survey plate is the sheet a surveyor draws for one place: the land at the
centre, the place name set large, the measurements written where they apply,
and a ledger at the edge saying who measured what. MAKAN screens are plates.

- **Place is the headline.** Screens open with where you are — the place name
  set in the display face, with the real map centre and scale — not with a slogan.
- **The map is the stage.** Discovery controls, results and the selected
  property are docked to the map's edges as one instrument, not floated over it.
- **Measurements are typography.** Prices, areas and counts are set in the
  display face with tabular figures; units are smaller. Price tags are survey
  annotations: a flat label with a pin stem, not a chat bubble.
- **The ledger.** Provenance (declared, verified, demo, estimate) is stated
  once, in words, in a ledger; objects carry at most one small demo mark.

## Tokens

### Colour

| Name           | Night (default)            | Day       | Role                                                               |
| -------------- | -------------------------- | --------- | ------------------------------------------------------------------ |
| Obsidian       | `#0B0F17`                  | ink       | Canvas (night), text (day)                                         |
| Charcoal       | `#161E2E`                  | —         | Docked consoles and raised surfaces (night)                        |
| Limestone      | `#EDE7DC`                  | `#F1F2EF` | Text (night), canvas (day): warm stone, not cream                  |
| Emerald        | `#10B981` / text `#34D399` | `#047857` | Doing: the one primary action and the selection. Never decoration. |
| River          | `#38BDD8`                  | `#0E7490` | Where: water, place glyphs, map layers only                        |
| Date-palm gold | `#C9A04E`                  | `#855E12` | Uncertain: demo, estimate, concept                                 |

Rules: one emerald fill per view; cyan never fills a button; gold never means "good".

### Type

- **Display — Alexandria** (variable, Arabic and Latin from one design):
  place names, page titles, prices and figures. Geometric, calm, built for both
  scripts, so the Arabic and English plates match.
- **Text — IBM Plex Sans Arabic** (400/500/600/700, Arabic and Latin): body,
  controls and tables. Engineered and compact; tabular figures for data.
- Scale (rem): 0.8125 · 0.875 · 1 · 1.125 · 1.375 · 1.75 · 2.25 · 3 · 4 · 5.5.
  Arabic display one step larger optically and with taller leading.
- No all-caps labels, no tracked eyebrows, no mono labels, sentence case only.

### Shape and depth

- Radii: 4 px tags · 8 px controls · 10 px photographs · 14 px phone sheets.
  Docked panels take no radius where they meet a screen or map edge.
- Depth by luminance (canvas → console → focus), one hairline at a docked
  edge. Shadows only on what floats over the map (tags, the selection).
- Blur only on small map overlays; never on reading surfaces.

### Motion

The camera is the only thing that travels: selection eases the map (≤ 900 ms),
preview → detail morphs the photograph, panels slide from the edge they are
docked to (240 ms). Everything else changes state in place (≤ 140 ms).
Reduced motion: instant camera, no morph, fades only.

## Principles

1. Answer where, what, which and next on the first screen of every flow.
2. Dock, don't float.
3. One emerald moment per view.
4. Say provenance once, in words.
5. Set numbers as measurements.
6. No duplicate photograph in one view: a repeated representative photo
   becomes a place plate (type, district and a map glyph) instead.
7. Fewer, larger decisions: remove a box before adding one.
