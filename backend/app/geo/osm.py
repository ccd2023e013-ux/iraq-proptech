"""Import real places (schools, hospitals, mosques, markets…) from OpenStreetMap.

Data comes from the public Overpass API as one bounded query per run (fair
use: a few requests a day, far below the documented limits). OSM data is
licensed under the ODbL, so every row carries ``source`` with the required
attribution and ``external_ref`` = ``osm:<type>/<id>`` for idempotent
refreshes. Nothing is scraped from any other service.

Safety: the endpoint is a constant (no user-supplied URL → no SSRF), the
bounding box must lie inside Iraq and be city-sized, responses are size-capped
and every name is treated as plain data (never as instructions or markup).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.geo.manage import IRAQ_LAT, IRAQ_LON
from app.geo.models import City
from app.geo.pois import PoiCategory, PointOfInterest
from app.geo.spatial import make_point

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "iraq-proptech/2.0 (+https://github.com/ccd2023e013-ux/iraq-proptech)"
OSM_SOURCE = "© OpenStreetMap contributors (ODbL)"
MAX_BBOX_DEG2 = 0.25  # about 50 km × 55 km — a city, not a country
MAX_RESPONSE_BYTES = 20_000_000
MAX_ITEMS = 5000

# City-proper extents (west, south, east, north) for cities we import by name.
CITY_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "basra": (47.70, 30.40, 47.92, 30.62),
}

Bbox = tuple[float, float, float, float]


@dataclass(frozen=True)
class OsmPlace:
    external_ref: str
    category: str
    name_ar: str
    name_en: str | None
    lon: float
    lat: float


_ARABIC = re.compile(r"[؀-ۿ]")
_CONTROL = re.compile(r"[\u0000-\u001f\u007f‪-‮⁦-⁩]")


def validate_bbox(bbox: Bbox) -> Bbox:
    west, south, east, north = bbox
    if not (west < east and south < north):
        raise ValueError("bbox must be west,south,east,north")
    if not (IRAQ_LON[0] <= west and east <= IRAQ_LON[1]):
        raise ValueError("bbox outside Iraq")
    if not (IRAQ_LAT[0] <= south and north <= IRAQ_LAT[1]):
        raise ValueError("bbox outside Iraq")
    if (east - west) * (north - south) > MAX_BBOX_DEG2:
        raise ValueError("bbox too large (city-sized areas only)")
    return bbox


def overpass_query(bbox: Bbox) -> str:
    west, south, east, north = validate_bbox(bbox)
    area = f"({south},{west},{north},{east})"
    selectors = [
        '["amenity"~"^(school|university|college|hospital|clinic|doctors|pharmacy|'
        'place_of_worship|marketplace|bank|fuel|bus_station|townhall|courthouse)$"]',
        '["shop"="mall"]',
        '["leisure"="park"]',
    ]
    parts = "".join(f"nwr{s}{area};" for s in selectors)
    return f"[out:json][timeout:120];({parts});out center tags {MAX_ITEMS};"


def classify(tags: dict[str, str]) -> str | None:
    amenity = tags.get("amenity")
    if amenity == "school":
        return PoiCategory.SCHOOL.value
    if amenity in ("university", "college"):
        return PoiCategory.UNIVERSITY.value
    if amenity == "hospital":
        return PoiCategory.HOSPITAL.value
    if amenity in ("clinic", "doctors"):
        return PoiCategory.CLINIC.value
    if amenity == "pharmacy":
        return PoiCategory.PHARMACY.value
    if amenity == "place_of_worship":
        religion = tags.get("religion")
        if religion == "muslim":
            return PoiCategory.MOSQUE.value
        if religion == "christian":
            return PoiCategory.CHURCH.value
        return None
    if amenity == "marketplace":
        return PoiCategory.MARKET.value
    if amenity == "bank":
        return PoiCategory.BANK.value
    if amenity == "fuel":
        return PoiCategory.FUEL.value
    if amenity == "bus_station":
        return PoiCategory.TRANSPORT.value
    if amenity in ("townhall", "courthouse"):
        return PoiCategory.GOVERNMENT.value
    if tags.get("shop") == "mall":
        return PoiCategory.MALL.value
    if tags.get("leisure") == "park":
        return PoiCategory.PARK.value
    return None


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    text = _CONTROL.sub("", value).strip()
    return text[:200] or None


def parse(elements: Iterable[dict[str, Any]], bbox: Bbox) -> list[OsmPlace]:
    """Named, categorised places inside ``bbox`` (unnamed features are skipped)."""
    west, south, east, north = bbox
    places: dict[str, OsmPlace] = {}
    for el in elements:
        kind, osm_id = el.get("type"), el.get("id")
        if kind not in ("node", "way", "relation") or not isinstance(osm_id, int):
            continue
        tags = {str(k): str(v) for k, v in (el.get("tags") or {}).items()}
        category = classify(tags)
        if category is None:
            continue
        point = el if kind == "node" else el.get("center") or {}
        lon, lat = point.get("lon"), point.get("lat")
        if not isinstance(lon, int | float) or not isinstance(lat, int | float):
            continue
        if not (west <= lon <= east and south <= lat <= north):
            continue
        name = _clean(tags.get("name"))
        name_ar = _clean(tags.get("name:ar")) or (name if name and _ARABIC.search(name) else None)
        name_en = _clean(tags.get("name:en")) or (
            name if name and not _ARABIC.search(name) else None
        )
        if not (name_ar or name_en):
            continue
        ref = f"osm:{kind}/{osm_id}"
        places[ref] = OsmPlace(
            external_ref=ref,
            category=category,
            name_ar=name_ar or name_en or "",
            name_en=name_en,
            lon=float(lon),
            lat=float(lat),
        )
    return list(places.values())[:MAX_ITEMS]


def fetch(bbox: Bbox, *, timeout: float = 180.0) -> list[dict[str, Any]]:
    """One Overpass request; returns the raw ``elements`` list."""
    with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        response = client.post(OVERPASS_URL, data={"data": overpass_query(bbox)})
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ValueError("Overpass response too large")
        data = response.json()
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list):
        raise ValueError("unexpected Overpass response")
    return elements


def import_places(
    db: Session,
    *,
    city_slug: str,
    bbox: Bbox | None = None,
    fetcher: Callable[[Bbox], list[dict[str, Any]]] = fetch,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upsert OSM places for a city; OSM places no longer present are deactivated."""
    area = validate_bbox(bbox or CITY_BBOXES[city_slug])
    city = db.execute(select(City).where(City.slug == city_slug)).scalars().first()
    if city is None:
        raise ValueError(f"unknown city {city_slug!r}")
    places = parse(fetcher(area), area)
    by_category: dict[str, int] = {}
    for p in places:
        by_category[p.category] = by_category.get(p.category, 0) + 1
    if dry_run:
        return {"city": city_slug, "found": len(places), "by_category": by_category}

    existing = {
        poi.external_ref: poi
        for poi in db.execute(
            select(PointOfInterest).where(
                PointOfInterest.external_ref.like("osm:%"),
                func.ST_Intersects(PointOfInterest.location, func.ST_MakeEnvelope(*area, 4326)),
            )
        ).scalars()
    }
    created = updated = 0
    for p in places:
        poi = existing.pop(p.external_ref, None)
        if poi is None:
            db.add(
                PointOfInterest(
                    id=uuid.uuid4(),
                    category=p.category,
                    name_ar=p.name_ar,
                    name_en=p.name_en,
                    location=make_point(p.lon, p.lat),
                    city_id=city.id,
                    source=OSM_SOURCE,
                    external_ref=p.external_ref,
                    is_demo=False,
                    is_active=True,
                )
            )
            created += 1
        else:
            poi.category, poi.name_ar, poi.name_en = p.category, p.name_ar, p.name_en
            poi.location = make_point(p.lon, p.lat)
            poi.is_active = True
            updated += 1
    gone = [poi.id for poi in existing.values()]
    if gone:
        db.execute(
            update(PointOfInterest).where(PointOfInterest.id.in_(gone)).values(is_active=False)
        )
    db.commit()
    return {
        "city": city_slug,
        "found": len(places),
        "created": created,
        "updated": updated,
        "deactivated": len(gone),
        "by_category": by_category,
        "source": OSM_SOURCE,
    }
