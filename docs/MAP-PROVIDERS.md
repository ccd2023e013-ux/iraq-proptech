# Map providers for Iraq — evaluation (Stage 3)

Checked October 2026 against each provider's public pricing/terms page (links
below). Prices and quotas change; re-check before signing up. Nothing here
requires a paid plan: the platform runs on the first row today.

## Decision

1. **Keep MapLibre GL JS + OpenFreeMap vector tiles** as the default basemap:
   no key, no account, no quota published, OSM data (good street coverage
   in Basra, Baghdad, Erbil, Sulaymaniyah), Arabic names rendered with the RTL
   text plugin. The light theme uses `liberty`; the dark theme uses OpenFreeMap
   `dark`, so the map follows the site theme.
2. **Satellite is optional and keyed** 🔑. The platform accepts any raster
   XYZ imagery source through configuration (`MAP_SATELLITE_TILES`,
   `MAP_SATELLITE_ATTRIBUTION`); the layer toggle only appears when one is
   configured. No free imagery source found allows commercial use without an
   account, so none is enabled by default.
3. **Places come from our own database**, never from a map provider's POI
   service: OSM-derived POIs imported with attribution (ODbL), plus clearly
   marked DEMO places where nothing real is loaded yet.
4. **Provider abstraction stays**: `MAP_PROVIDER`, `MAP_STYLE_URL`,
   `MAP_DARK_STYLE_URL`, `MAP_SATELLITE_*` are runtime environment values
   (frontend/src/lib/map/provider.ts); switching provider is configuration.
   On the production PC the same style can be served from self-hosted PMTiles.

## Comparison

| Provider | Free allowance | Commercial use on free | Satellite | Geocoding / POI | Account / key | Notes for Iraq |
| --- | --- | --- | --- | --- | --- | --- |
| **OpenFreeMap** (MapLibre) | No published quota | Not restricted by its ToS | No | No (use own data) | None | ToS: may be discontinued without notice, no SLA → keep the style swappable. Styles: positron, bright, liberty, dark, fiord, 3d. |
| OSM Foundation raster tiles | Light use only | Heavy use discouraged; may be blocked | No | No | None | Fallback only (`MAP_PROVIDER=osm-raster`); requires visible attribution and a proper User-Agent. |
| Protomaps / PMTiles (self-hosted) | Unlimited (own hosting) | Yes (OSM data, ODbL) | No | No | None | Best option for the production PC: one file, no third party at runtime. |
| MapTiler Cloud | 5k map sessions, 100k requests, 1k search sessions / month | **No** (free plan is non-commercial) | Yes | Yes | Key (in URL) | Commercial needs Flex, $30/month. |
| Mapbox | 50k GL JS map loads, 100k geocoding requests, 750k raster tile requests / month | Yes, with account | Yes | Yes | Public token | Terms require Mapbox SDK or raster API attribution; would be the first paid-tier candidate for satellite. |
| Apple MapKit JS | 250k map views + 25k service calls per day | Yes | Yes | Yes (Apple Maps search) | Apple Developer Program membership (paid yearly) + JWT signing server | Not MapLibre — a second renderer to maintain; Iraq detail varies by city. |
| Esri / ArcGIS Location Platform | 1,000 basemap sessions / month | Account required | World Imagery | Yes | Token | Quota too small for a public site. |
| TomTom | 200k map display, 20k routing, 5–10k search requests / month | Check terms | Limited | Yes | Key, no card | Traffic and routing would come from here if ever needed. |
| HERE | Free tier with signup | Check terms | Yes | Yes | Key | Pricing page did not list figures publicly at review time. |
| EOX Sentinel-2 cloudless | Free | **No** (non-commercial only) | 10 m imagery | No | None | Fine for a private demo, not for a commercial site. |
| Google Maps | — | — | — | — | — | Excluded: its tiles may only be shown in Google's own map, and scraping it is prohibited. |

## What we need from a provider, and who supplies it

| Need | Supplied by |
| --- | --- |
| Street basemap, Arabic labels, light + dark | OpenFreeMap (MapLibre), RTL text plugin |
| Satellite | Optional keyed raster source 🔑 (Mapbox or MapTiler paid), off by default |
| Areas / districts | Our PostGIS boundaries (DEMO-labelled until official geometry exists) |
| Schools, hospitals, mosques, markets… | Our POI table: OSM import (ODbL attribution) + DEMO places |
| Geocoding of typed places | Our gazetteer (governorates, cities, districts) and search |
| Routing / traffic | Not needed now; TomTom or Mapbox when a feature needs it 🔑 |

## Attribution rules implemented

- The map's attribution control always shows the basemap credit
  ("OpenFreeMap © OpenMapTiles, data © OpenStreetMap contributors").
- The POI layer adds "© OpenStreetMap contributors (ODbL)" while OSM places
  are on screen, and DEMO places are labelled "demo" in every list.
- A configured satellite source must provide `MAP_SATELLITE_ATTRIBUTION`;
  without it the satellite toggle is not offered.

## Sources

- OpenFreeMap quick start and terms: https://openfreemap.org/quick_start/ ·
  https://openfreemap.org/tos/
- OSMF tile usage policy: https://operations.osmfoundation.org/policies/tiles/
- MapTiler pricing: https://www.maptiler.com/cloud/pricing/
- Mapbox pricing: https://www.mapbox.com/pricing
- Apple MapKit JS: https://developer.apple.com/maps/web/
- Esri basemap sessions: https://www.esri.com/arcgis-blog/products/platform/announcements/basemap-sessions
- TomTom pricing: https://docs.tomtom.com/pricing
- EOX cloudless viewing: https://cloudless.eox.at/products/viewing
- Overpass API fair use: https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
