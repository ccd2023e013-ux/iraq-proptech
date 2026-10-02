# GIS and maps

PostGIS (WGS84, EPSG:4326) is the source of truth for every location; the
browser renders with [MapLibre GL JS](https://maplibre.org/) (open source, no
API key). Nothing is Basra-specific: Basra is simply the first data set and the
default viewport (`MAP_DEFAULT_BBOX`).

## Data model

| Table | Geometry | Notes |
| --- | --- | --- |
| `governorates`, `cities`, `districts`, `neighborhoods` | `centroid` POINT, `boundary` MULTIPOLYGON (both optional) | `geometry_source` records where a shape came from; GIST index on `boundary` |
| `properties` | `location` POINT (exact, private) and `display_location` POINT (public) | GIST indexes on both |

Shipped reference data contains **centroids only** (marked approximate).
No boundary polygons are bundled because no verified, openly-licensed
Iraqi administrative-boundary dataset is included in the repository. Real
boundaries are imported through the admin API (below), with their licence in
`geometry_source` (for example `OpenStreetMap contributors (ODbL)`).

## Location privacy

The exact `location` never leaves the API for the public. `display_location`
is derived server-side:

| `location_privacy` | Public point |
| --- | --- |
| `EXACT` | the exact point |
| `APPROXIMATE` | neighborhood centroid when known, otherwise the centre of a 0.005° grid cell (≈ 550 m) — identical for every point in that cell |
| `HIDDEN` | none — the listing is not on the map and is excluded from spatial filters |

All spatial search, map and clustering queries use `display_location` only,
so a bounding box or polygon can never be used to triangulate a hidden house.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /map/properties?{search filters}&bbox=w,s,e,n&zoom=z` | GeoJSON `FeatureCollection` for the viewport. Up to 1,500 matches → points with popup fields (title, price + currency, type, rooms, area, verified, demo, approximate, cover thumbnail). More → server-side clusters (`ST_SnapToGrid`, cell ≈ 60 px at `zoom`) with `point_count` and member `bbox`. `meta` says which. |
| `GET /search/properties?bbox=…` / `near_lat,near_lon,radius_km` / `polygon=lon,lat;…` | Same spatial filters for the list (radius uses geography distance in metres; polygons are repaired with `ST_MakeValid`). |
| `GET /locations/{level}/{id}/geojson` | A place as a Feature: its boundary, or its centroid point when it has none (`has_boundary=false`). |
| `GET /locations/boundaries?level=districts&parent_id=…&simplify=0.0001` | Boundaries of the children of a place (simplified with topology preserved). |
| `GET /locations/resolve?lat=…&lon=…` | Which neighborhood/district/city/governorate contains a point. Uses boundaries (`method=boundary`), else the nearest city centroid within 40 km (`method=nearest_city_centroid`, `approximate=true`), else `method=none`. Points outside Iraq → `422 OUTSIDE_IRAQ`. Never guesses beyond that. |
| `POST /admin/locations/{cities\|districts\|neighborhoods}` | Create a place (optional centroid and boundary). Permission `locations.manage` (ADMIN, SUPER_ADMIN). Audited. |
| `PUT /admin/locations/{level}/{id}/boundary` | Set a boundary from GeoJSON `Polygon`/`MultiPolygon` + `source`. Validated: closed rings, numeric coordinates inside Iraq (catches lat/lon swaps), ≤ 20,000 vertices; repaired with `ST_MakeValid`, stored as MULTIPOLYGON; empty results rejected. Audited. |
| `DELETE /admin/locations/{level}/{id}/boundary` | Remove a boundary. Audited. |

Level names: `governorates`, `cities`, `districts`, `neighborhoods`.
Governorates are fixed reference data (19) and cannot be created via the API.

### Importing real boundaries

1. Obtain a dataset whose licence allows your use (e.g. OSM administrative
   boundaries via an extract, ODbL — attribution required).
2. Convert each area to GeoJSON in EPSG:4326 (`ogr2ogr -t_srs EPSG:4326 -f GeoJSON …`).
3. Create missing districts/neighborhoods with `POST /admin/locations/…`,
   then `PUT …/boundary` with `source` set to the dataset and licence.

## Map provider abstraction

The basemap is configuration read by the frontend server at request time
(`frontend/src/lib/map/provider.ts`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAP_PROVIDER` | `openfreemap` | `openfreemap` (free vector tiles, no key, no usage fees), `osm-raster` (OpenStreetMap tiles — development only, per the OSM tile usage policy) or `custom` |
| `MAP_STYLE_URL` | — | Any MapLibre style JSON; overrides `MAP_PROVIDER`. Use this for self-hosted tiles (e.g. Protomaps PMTiles) on the production PC. |
| `MAP_ATTRIBUTION` | OSM attribution | Attribution for custom styles |
| `MAP_DEFAULT_BBOX` | all of Iraq | Initial viewport `w,s,e,n` (`.env.example` sets Basra) |
| `MAP_RTL_PLUGIN_URL` | MapLibre/Mapbox RTL text plugin on unpkg | Arabic shaping for vector labels; empty disables |

No Google Maps data is scraped or used, and no satellite imagery with
restrictive terms is included. Switching provider never requires code
changes.

## Web UI

- `/map`: filters, a results list and the map side by side (tabs on
  phones). Moving the map writes `bbox` to the URL (debounced); the server
  re-renders the list for that viewport and the map loads GeoJSON for the
  same filters — list and map always describe the same search, and the URL
  is shareable. "Draw an area" replaces the viewport with a polygon filter.
  Hovering a list item highlights its marker; clicking a marker highlights
  the list item and opens a text-only popup. Clusters zoom in on click.
  Approximate locations are drawn as softer markers; demo listings in grey.
  Boundary sources are listed under the map, with a warning for DEMO shapes.
- Listing form: a location picker (click or drag the marker). The containing
  area is *suggested* via `/locations/resolve`; the lister applies it
  explicitly.

## DEMO data

`python -m app.cli seed-demo [--listings 40]` (refused in production unless
`--allow-production`) creates, idempotently:

- eight Basra districts with real names, **approximate** centres and ~1 km
  square placeholder boundaries labelled
  `DEMO — approximate square, not an official boundary`;
- demo listings (`is_demo=true`, "تجريبي" in the title, a "not a real offer"
  description, no photos) spread inside those squares.

`python -m app.cli reset-demo` deletes the demo listings.

## Tests

`backend/tests/test_gis.py` covers public-only points, privacy, filters on
the map endpoint, server clustering, radius/polygon across Basra, Baghdad,
Erbil and Mosul, boundary creation and validation (unclosed rings,
coordinates outside Iraq, lat/lon swap, non-numeric values, self-intersection
repair), permissions, audit, point resolution (boundary, nearest-centroid
fallback, a point in Kuwait inside Iraq's bounding box → `none`, Tehran →
422) and the demo seed. `scripts/ci/smoke-map.sh` runs the same flow
against the Docker stack.
