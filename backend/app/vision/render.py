"""Deterministic concept renderer (the built-in, key-free vision provider).

Draws an isometric *massing* illustration from the brief — plot, building
volumes per floor, landscaping, parking — in two variants:

* ``concept``: the building on its plot;
* ``vision``: the same building from the street with neighbours, road and
  palms, to imagine the future streetscape.

It is an illustration of the brief, not a design: no structure, services,
setbacks or regulations are checked. Every image carries the AI CONCEPT
label burned into the pixels, so it stays with the picture when shared.
"""

from __future__ import annotations

import hashlib
import io
import math
import random
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

BuildingType = Literal["house", "villa", "apartments", "commercial", "mixed_use"]
Style = Literal["modern", "traditional", "courtyard", "minimal"]
Variant = Literal["concept", "vision"]

LABEL = "AI CONCEPT - NOT AN ENGINEERING OR GOVERNMENT APPROVAL"
WIDTH, HEIGHT = 1600, 1000
BAND = 92
FLOOR_HEIGHT_M = 3.3

COVERAGE: dict[str, float] = {
    "house": 0.55,
    "villa": 0.45,
    "apartments": 0.55,
    "commercial": 0.7,
    "mixed_use": 0.6,
}

PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "modern": {"wall": (236, 238, 236), "accent": (52, 120, 112), "roof": (250, 250, 248)},
    "traditional": {"wall": (222, 196, 158), "accent": (150, 98, 56), "roof": (236, 214, 178)},
    "courtyard": {"wall": (230, 210, 176), "accent": (120, 92, 60), "roof": (242, 226, 196)},
    "minimal": {"wall": (246, 246, 244), "accent": (70, 74, 78), "roof": (255, 255, 255)},
}


@dataclass(frozen=True)
class Brief:
    building_type: BuildingType
    floors: int
    style: Style
    plot_width_m: float
    plot_depth_m: float
    landscaping: bool = True
    parking: bool = True
    pool: bool = False
    shops_ground_floor: bool = False

    def seed(self) -> int:
        return int(hashlib.sha256(repr(self).encode()).hexdigest()[:8], 16)


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)  # type: ignore[return-value]


class _Iso:
    """Isometric projection fitted to the scene size (metres → pixels)."""

    def __init__(self, extent_m: float, height_m: float, origin_y: float) -> None:
        usable_w = WIDTH * 0.8
        self.scale = usable_w / (extent_m * 2 * math.cos(math.radians(30)))
        max_h = (HEIGHT - BAND) * 0.42
        if height_m * self.scale > max_h:
            self.scale = max_h / height_m
        self.cx = WIDTH / 2
        self.cy = origin_y

    def p(self, x: float, y: float, z: float = 0.0) -> tuple[float, float]:
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        return (
            self.cx + (x - y) * c * self.scale,
            self.cy + (x + y) * s * self.scale - z * self.scale,
        )


def _box(
    draw: ImageDraw.ImageDraw,
    iso: _Iso,
    x: float,
    y: float,
    w: float,
    d: float,
    z0: float,
    h: float,
    color: tuple[int, int, int],
) -> None:
    p = iso.p
    top = [p(x, y, z0 + h), p(x + w, y, z0 + h), p(x + w, y + d, z0 + h), p(x, y + d, z0 + h)]
    left = [p(x, y + d, z0), p(x + w, y + d, z0), p(x + w, y + d, z0 + h), p(x, y + d, z0 + h)]
    right = [p(x + w, y, z0), p(x + w, y + d, z0), p(x + w, y + d, z0 + h), p(x + w, y, z0 + h)]
    edge = _shade(color, 0.55)
    draw.polygon(left, fill=_shade(color, 0.8), outline=edge)
    draw.polygon(right, fill=_shade(color, 0.92), outline=edge)
    draw.polygon(top, fill=_shade(color, 1.04), outline=edge)


def _windows(
    draw: ImageDraw.ImageDraw,
    iso: _Iso,
    x: float,
    y: float,
    w: float,
    d: float,
    floors: int,
    glass: tuple[int, int, int],
    start_floor: int = 0,
) -> None:
    for f in range(start_floor, floors):
        z = f * FLOOR_HEIGHT_M + 1.0
        # front-left face (y = y + d), windows every ~3 m
        n = max(1, int(w // 3.2))
        for i in range(n):
            wx = x + (i + 0.3) * w / n
            quad = [
                iso.p(wx, y + d, z),
                iso.p(wx + w / n * 0.45, y + d, z),
                iso.p(wx + w / n * 0.45, y + d, z + 1.5),
                iso.p(wx, y + d, z + 1.5),
            ]
            draw.polygon(quad, fill=_shade(glass, 0.9))
        m = max(1, int(d // 3.2))
        for i in range(m):
            wy = y + (i + 0.3) * d / m
            quad = [
                iso.p(x + w, wy, z),
                iso.p(x + w, wy + d / m * 0.45, z),
                iso.p(x + w, wy + d / m * 0.45, z + 1.5),
                iso.p(x + w, wy, z + 1.5),
            ]
            draw.polygon(quad, fill=glass)


def _tree(draw: ImageDraw.ImageDraw, iso: _Iso, x: float, y: float, palm: bool) -> None:
    bx, by = iso.p(x, y, 0)
    tx, ty = iso.p(x, y, 5.5 if palm else 4.0)
    draw.line([(bx, by), (tx, ty)], fill=(120, 92, 60), width=max(2, int(iso.scale * 0.25)))
    r = iso.scale * (1.6 if palm else 2.0)
    if palm:
        for k in range(7):
            a = math.radians(k * 360 / 7)
            draw.line(
                [(tx, ty), (tx + math.cos(a) * r, ty + math.sin(a) * r * 0.5 + r * 0.25)],
                fill=(58, 128, 72),
                width=max(2, int(iso.scale * 0.3)),
            )
    else:
        draw.ellipse([tx - r, ty - r, tx + r, ty + r * 0.8], fill=(86, 150, 92))


def render(brief: Brief, variant: Variant) -> bytes:
    """PNG bytes of the illustration (deterministic for a given brief and variant)."""
    # Layout variety only (tree positions), not security-relevant.
    rng = random.Random(brief.seed() + (1 if variant == "vision" else 0))  # noqa: S311
    pw, pd = brief.plot_width_m, brief.plot_depth_m
    height_m = brief.floors * FLOOR_HEIGHT_M + 2
    extent = max(pw, pd) * (1.9 if variant == "vision" else 1.25)
    img = Image.new("RGB", (WIDTH, HEIGHT), (236, 241, 243))
    draw = ImageDraw.Draw(img)
    # sky gradient
    for yy in range(HEIGHT - BAND):
        t = yy / (HEIGHT - BAND)
        draw.line(
            [(0, yy), (WIDTH, yy)],
            fill=(int(206 + 34 * t), int(224 + 18 * t), int(236 + 8 * t)),
        )
    ox = -pw / 2
    oy = -pd / 2
    iso = _Iso(extent, height_m, origin_y=0)
    avail = HEIGHT - BAND
    probe = [iso.p(ox, oy, height_m), iso.p(ox + pw, oy + pd, 0), iso.p(ox + pw, oy, height_m)]
    probe += [iso.p(ox, oy + pd, 0)]
    if variant == "vision":
        probe += [iso.p(0, oy + pd + 12, 0)]
    top, bottom = min(y for _, y in probe), max(y for _, y in probe)
    if bottom - top > avail * 0.86:
        iso.scale *= avail * 0.86 / (bottom - top)
        probe_scaled = [iso.p(ox, oy, height_m), iso.p(ox + pw, oy + pd, 0)]
        top = min(y for _, y in probe_scaled)
        bottom = max(y for _, y in probe_scaled)
    iso.cy = (avail - (top + bottom)) / 2

    if variant == "vision":
        # ground, road in front (along +y edge), sidewalk, neighbours
        g = extent
        draw.polygon([iso.p(-g, -g), iso.p(g, -g), iso.p(g, g), iso.p(-g, g)], fill=(214, 206, 186))
        road_y = oy + pd + 3
        draw.polygon(
            [iso.p(-g, road_y), iso.p(g, road_y), iso.p(g, road_y + 9), iso.p(-g, road_y + 9)],
            fill=(92, 96, 100),
        )
        for k in range(-int(g), int(g), 6):
            draw.line(
                [iso.p(k, road_y + 4.5), iso.p(k + 3, road_y + 4.5)], fill=(236, 236, 220), width=3
            )
        draw.polygon(
            [iso.p(-g, oy + pd), iso.p(g, oy + pd), iso.p(g, road_y), iso.p(-g, road_y)],
            fill=(200, 196, 188),
        )
        for side in (-1, 1):
            nx = ox + side * (pw + 4) if side > 0 else ox - pw * 0.9 - 4
            nh = rng.choice([2, 2, 3]) * FLOOR_HEIGHT_M
            _box(draw, iso, nx, oy + 2, pw * 0.9, pd * 0.7, 0, nh, (200, 202, 204))
        for k in range(-int(g), int(g), 9):
            _tree(draw, iso, k + 2, road_y - 1.2, palm=True)
    else:
        draw.polygon(
            [
                iso.p(-extent, -extent),
                iso.p(extent, -extent),
                iso.p(extent, extent),
                iso.p(-extent, extent),
            ],
            fill=(222, 216, 200),
        )

    # plot with boundary
    plot = [iso.p(ox, oy), iso.p(ox + pw, oy), iso.p(ox + pw, oy + pd), iso.p(ox, oy + pd)]
    draw.polygon(plot, fill=(206, 222, 196) if brief.landscaping else (226, 220, 204))
    for a, b in zip(plot, plot[1:] + plot[:1], strict=True):
        steps = 24
        for i in range(0, steps, 2):
            p1 = (a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
            p2 = (a[0] + (b[0] - a[0]) * (i + 1) / steps, a[1] + (b[1] - a[1]) * (i + 1) / steps)
            draw.line([p1, p2], fill=(150, 112, 40), width=3)

    palette = PALETTES[brief.style]
    cov = COVERAGE[brief.building_type]
    bw, bd = pw * math.sqrt(cov), pd * math.sqrt(cov)
    bx, by = ox + (pw - bw) * 0.5, oy + (pd - bd) * 0.35

    if brief.parking:
        px, py = ox + 1, oy + pd - 5.5
        draw.polygon(
            [
                iso.p(px, py),
                iso.p(px + min(pw - 2, 12), py),
                iso.p(px + min(pw - 2, 12), py + 5),
                iso.p(px, py + 5),
            ],
            fill=(150, 152, 150),
        )
        for k in range(int(min(pw - 2, 12) // 2.6)):
            line = [iso.p(px + k * 2.6, py), iso.p(px + k * 2.6, py + 5)]
            draw.line(line, fill=(240, 240, 240), width=2)
    if brief.pool:
        qx, qy = bx + bw + 1 if bx + bw + 5 < ox + pw else ox + 1, oy + 1
        draw.polygon(
            [iso.p(qx, qy), iso.p(qx + 4, qy), iso.p(qx + 4, qy + 7), iso.p(qx, qy + 7)],
            fill=(110, 186, 214),
        )

    # Trees: those behind the building are drawn first (painter's order).
    palm = brief.style in ("traditional", "courtyard")
    trees: list[tuple[float, float]] = []
    if brief.landscaping:
        for _ in range(6 if variant == "concept" else 4):
            tx = ox + rng.uniform(0.5, pw - 0.5)
            ty = oy + rng.choice([rng.uniform(0.3, 1.5), rng.uniform(pd - 1.5, pd - 0.3)])
            trees.append((tx, ty))
    centre = (bx + bw / 2) + (by + bd / 2)
    trees_front = [t for t in trees if t[0] + t[1] > centre]
    for tx, ty in (t for t in trees if t[0] + t[1] <= centre):
        _tree(draw, iso, tx, ty, palm=palm)

    floors = brief.floors
    ground_glass = brief.shops_ground_floor or brief.building_type in ("commercial", "mixed_use")
    if ground_glass:
        _box(draw, iso, bx, by, bw, bd, 0, FLOOR_HEIGHT_M, _shade(palette["accent"], 1.25))
        _windows(draw, iso, bx, by, bw, bd, 1, (170, 214, 220))
        start = 1
    else:
        start = 0
    if floors > start:
        if brief.style == "courtyard" and bw > 9 and bd > 9:
            t = min(bw, bd) * 0.3
            z0 = start * FLOOR_HEIGHT_M
            h = (floors - start) * FLOOR_HEIGHT_M
            wings = [
                (bx, by, bw, t),
                (bx, by, t, bd),
                (bx + bw - t, by, t, bd),
                (bx, by + bd - t, bw, t),
            ]
            wings.sort(key=lambda b: (b[0] + b[2] / 2) + (b[1] + b[3] / 2))  # back to front
            for wx, wy, ww, wd in wings:
                _box(draw, iso, wx, wy, ww, wd, z0, h, palette["wall"])
        else:
            _box(
                draw,
                iso,
                bx,
                by,
                bw,
                bd,
                start * FLOOR_HEIGHT_M,
                (floors - start) * FLOOR_HEIGHT_M,
                palette["wall"],
            )
        _windows(draw, iso, bx, by, bw, bd, floors, (120, 168, 182), start_floor=start)
        if not (brief.style == "courtyard" and bw > 9 and bd > 9):
            # roof parapet (a courtyard stays open to the sky)
            _box(draw, iso, bx, by, bw, bd, floors * FLOOR_HEIGHT_M, 0.6, palette["roof"])

    for tx, ty in trees_front:
        _tree(draw, iso, tx, ty, palm=palm)

    # label band (burned in)
    draw.rectangle([0, HEIGHT - BAND, WIDTH, HEIGHT], fill=(16, 32, 30))
    draw.text((32, HEIGHT - BAND + 14), LABEL, fill=(255, 205, 96), font=_font(30))
    floors_text = f"{brief.floors} floor{'s' if brief.floors > 1 else ''}"
    plot_text = f"plot {brief.plot_width_m:g} x {brief.plot_depth_m:g} m"
    sub = (
        f"Illustrative massing of your brief ({brief.building_type}, {floors_text}, "
        f"{plot_text}) - not a design, structural or legal assessment"
    )
    draw.text((32, HEIGHT - BAND + 54), sub, fill=(214, 226, 222), font=_font(20))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def burn_label(image_bytes: bytes) -> bytes:
    """Add the AI CONCEPT band to an image from an external provider."""
    src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = src.size
    band = max(48, h // 12)
    out = Image.new("RGB", (w, h + band), (16, 32, 30))
    out.paste(src, (0, 0))
    ImageDraw.Draw(out).text(
        (24, h + band // 4), LABEL, fill=(255, 205, 96), font=_font(max(16, band // 3))
    )
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
