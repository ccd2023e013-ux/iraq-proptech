"""Deterministic, clearly-labelled DEMO illustrations for demo listings.

No photographs are used or downloaded: each image is a flat illustration drawn
with Pillow from the listing's type and a seed, with a large "DEMO" label and
"SYNTHETIC IMAGE" caption burned in, so it can never pass for a real photo of
a real property. The same (type, seed) always produces the same image.
"""

from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 800

# Muted palettes (sky top, sky bottom, ground) per city "mood" — purely decorative.
_SKIES = [
    ((176, 214, 236), (236, 228, 205), (214, 192, 150)),  # warm desert
    ((160, 200, 230), (226, 236, 240), (196, 186, 160)),  # clear
    ((190, 210, 225), (240, 222, 196), (205, 178, 138)),  # dusk
    ((150, 190, 222), (232, 240, 236), (170, 186, 140)),  # green (north)
]
_WALLS = [(222, 205, 176), (236, 226, 208), (205, 186, 160), (214, 214, 206), (232, 214, 190)]
_ACCENTS = [(46, 98, 120), (128, 74, 52), (70, 110, 80), (150, 120, 60), (90, 90, 120)]


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow without FreeType sizing
        return ImageFont.load_default()


def _gradient(draw: ImageDraw.ImageDraw, top: tuple, bottom: tuple, height: int) -> None:
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color)


def _windows(
    draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, cols: int, rows: int, color
) -> None:
    w = (x1 - x0) / (cols * 2 + 1)
    h = (y1 - y0) / (rows * 2 + 1)
    for r in range(rows):
        for c in range(cols):
            wx = x0 + w * (c * 2 + 1)
            wy = y0 + h * (r * 2 + 1)
            draw.rectangle([wx, wy, wx + w, wy + h], fill=color)


def _house(draw, rng, wall, accent, ground_y, *, wide: bool = False) -> None:
    width = rng.randint(420, 520) + (220 if wide else 0)
    height = rng.randint(220, 280)
    x0 = (WIDTH - width) // 2 + rng.randint(-60, 60)
    x1, y1 = x0 + width, ground_y
    y0 = y1 - height
    draw.rectangle([x0, y0, x1, y1], fill=wall, outline=(120, 100, 80), width=3)
    # Flat roof parapet (common in Iraq) or a pitched roof.
    if rng.random() < 0.6:
        draw.rectangle([x0 - 10, y0 - 22, x1 + 10, y0], fill=accent)
    else:
        draw.polygon([(x0 - 30, y0), ((x0 + x1) // 2, y0 - 120), (x1 + 30, y0)], fill=accent)
    _windows(
        draw, x0, y0 + 20, x1, y1 - 70, cols=3 if not wide else 5, rows=1, color=(80, 120, 150)
    )
    door_w = 70
    dx = (x0 + x1) // 2 - door_w // 2
    draw.rectangle([dx, y1 - 120, dx + door_w, y1], fill=(110, 80, 60))
    if wide:  # garden
        for i in range(6):
            gx = x0 - 160 + i * 40
            draw.ellipse([gx, y1 - 70, gx + 50, y1 - 10], fill=(80, 140, 80))


def _apartment(draw, rng, wall, accent, ground_y) -> None:
    for b in range(rng.randint(2, 3)):
        width = rng.randint(220, 280)
        height = rng.randint(360, 520)
        x0 = 140 + b * 330 + rng.randint(-20, 20)
        draw.rectangle(
            [x0, ground_y - height, x0 + width, ground_y], fill=wall, outline=accent, width=4
        )
        _windows(
            draw,
            x0,
            ground_y - height,
            x0 + width,
            ground_y - 40,
            cols=3,
            rows=6,
            color=(80, 120, 150),
        )


def _land(draw, rng, ground_y) -> None:
    # A marked plot: survey pegs and a dashed boundary on open ground.
    x0, x1 = 220 + rng.randint(-40, 40), 980 + rng.randint(-40, 40)
    y0, y1 = ground_y + 25, HEIGHT - 75
    for x in range(x0, x1, 40):
        draw.line([(x, y0), (x + 20, y0)], fill=(120, 60, 40), width=5)
        draw.line([(x, y1), (x + 20, y1)], fill=(120, 60, 40), width=5)
    for y in range(y0, y1, 40):
        draw.line([(x0, y), (x0, y + 20)], fill=(120, 60, 40), width=5)
        draw.line([(x1, y), (x1, y + 20)], fill=(120, 60, 40), width=5)
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        draw.rectangle([x - 8, y - 30, x + 8, y], fill=(200, 60, 40))


def _shop(draw, rng, wall, accent, ground_y, *, office: bool = False) -> None:
    width = rng.randint(620, 760)
    x0 = (WIDTH - width) // 2
    height = 420 if office else 260
    y0 = ground_y - height
    draw.rectangle([x0, y0, x0 + width, ground_y], fill=wall, outline=accent, width=4)
    if office:
        _windows(draw, x0, y0, x0 + width, ground_y - 30, cols=6, rows=4, color=(110, 150, 180))
    else:
        # Awning stripes and a shop window.
        for i in range(0, width, 60):
            color = accent if (i // 60) % 2 == 0 else (240, 240, 235)
            draw.rectangle([x0 + i, y0 + 40, x0 + min(i + 60, width), y0 + 90], fill=color)
        draw.rectangle([x0 + 40, y0 + 120, x0 + width - 200, ground_y - 20], fill=(150, 185, 205))
        draw.rectangle([x0 + width - 160, y0 + 120, x0 + width - 60, ground_y], fill=(110, 80, 60))


def render(property_type: str, seed: int) -> bytes:
    """PNG bytes of a synthetic illustration for ``property_type``."""
    rng = random.Random(f"{property_type}:{seed}")  # noqa: S311 - decoration only
    sky_top, sky_bottom, ground = _SKIES[seed % len(_SKIES)]
    wall = rng.choice(_WALLS)
    accent = rng.choice(_ACCENTS)
    image = Image.new("RGB", (WIDTH, HEIGHT), sky_bottom)
    draw = ImageDraw.Draw(image)
    ground_y = int(HEIGHT * rng.uniform(0.66, 0.74))
    _gradient(draw, sky_top, sky_bottom, ground_y)
    draw.rectangle([0, ground_y, WIDTH, HEIGHT], fill=ground)
    # A palm or two — a recognisable, generic Iraqi landscape cue.
    for _ in range(rng.randint(1, 3)):
        px = rng.choice([rng.randint(30, 160), rng.randint(1040, 1170)])
        draw.rectangle([px, ground_y - 260, px + 14, ground_y], fill=(120, 90, 60))
        for angle in range(6):
            dx = (angle - 2.5) * 40
            draw.line(
                [(px + 7, ground_y - 260), (px + 7 + dx, ground_y - 200 - abs(dx) / 3)],
                fill=(70, 130, 70),
                width=10,
            )

    if property_type in ("HOUSE",):
        _house(draw, rng, wall, accent, ground_y)
    elif property_type in ("VILLA", "FARM"):
        _house(draw, rng, wall, accent, ground_y, wide=True)
    elif property_type in ("APARTMENT", "BUILDING"):
        _apartment(draw, rng, wall, accent, ground_y)
    elif property_type == "LAND":
        _land(draw, rng, ground_y)
    elif property_type in ("OFFICE",):
        _shop(draw, rng, wall, accent, ground_y, office=True)
    else:
        _shop(draw, rng, wall, accent, ground_y)

    # Unmistakable labels.
    draw.rectangle([0, 0, WIDTH, 96], fill=(30, 30, 30))
    draw.text((32, 18), "DEMO", fill=(255, 196, 0), font=_font(60))
    draw.text(
        (250, 34), "SYNTHETIC IMAGE - NOT A REAL PROPERTY", fill=(255, 255, 255), font=_font(30)
    )
    draw.rectangle([0, HEIGHT - 50, WIDTH, HEIGHT], fill=(30, 30, 30))
    draw.text(
        (32, HEIGHT - 42),
        f"MAKAN demo illustration #{seed}",
        fill=(220, 220, 220),
        font=_font(26),
    )

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()
