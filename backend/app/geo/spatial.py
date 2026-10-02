"""Spatial helpers that avoid heavy GIS dependencies in the API process."""

from __future__ import annotations

import struct
from typing import Any

from geoalchemy2 import WKTElement

from app.geo.models import SRID

APPROXIMATE_GRID_DEGREES = 0.005  # ≈ 550 m north–south; coarse enough to hide a house


def make_point(lon: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lon:.7f} {lat:.7f})", srid=SRID)


def point_lonlat(value: Any) -> tuple[float, float] | None:
    """(lon, lat) from a PostGIS point returned by GeoAlchemy2 (EWKB) or WKT element."""
    if value is None:
        return None
    if isinstance(value, WKTElement):
        inner = str(value.data).split("(", 1)[1].rstrip(")")
        lon_s, lat_s = inner.split()
        return float(lon_s), float(lat_s)
    raw = getattr(value, "data", value)
    data = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
    order = "<" if data[0] == 1 else ">"
    (geom_type,) = struct.unpack(order + "I", data[1:5])
    offset = 9 if geom_type & 0x20000000 else 5  # skip SRID when present (EWKB)
    if geom_type & 0xFFFF not in (1,):
        raise ValueError("Not a point geometry")
    lon, lat = struct.unpack(order + "dd", data[offset : offset + 16])
    return lon, lat


def coarsen(lon: float, lat: float, grid: float = APPROXIMATE_GRID_DEGREES) -> tuple[float, float]:
    """Snap to the centre of a grid cell: same output for every point in the cell."""

    def snap(v: float) -> float:
        return round((v // grid) * grid + grid / 2, 6)

    return snap(lon), snap(lat)
