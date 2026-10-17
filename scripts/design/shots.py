"""Design review screenshots of the running app (design preview workflow).

Captures key pages in Arabic RTL and English LTR, dark (default) and light,
at 1920 / 1440 / 390 px, plus a few signed-in screens, and records console
errors and failed requests per page. Writes JPEGs and report.json to OUT.

    WEB_URL=http://localhost:3000 OUT=/tmp/shots python scripts/design/shots.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

WEB = os.environ.get("WEB_URL", "http://localhost:3000").rstrip("/")
OUT = Path(os.environ.get("OUT", "/tmp/shots"))
FULL = os.environ.get("FULL", "1") == "1"
MAX_H = 3200  # cap very long pages (px, CSS)

PUBLIC = [
    ("home", "/"),
    ("map", "/map"),
    ("properties", "/properties"),
    ("listing", None),  # first listing, resolved at run time
    ("future", "/future"),
    ("market", "/market"),
    ("pricing", "/pricing"),
    ("login", "/login"),
    ("register", "/register"),
    ("smart", "/search/smart"),
    ("compare", "/compare"),
    ("compare-3", None),  # three listings, resolved at run time
    ("flight", None),  # the first listing's drone flight, resolved at run time
    ("studio", "/studio"),
    ("vision", "/vision"),
    ("credits", "/credits"),
    ("status", "/status"),
    ("forgot", "/forgot-password"),
    ("notfound", "/this-page-does-not-exist"),
]
SIGNED_IN = [
    (
        "agent",
        "demo.agent@example.com",
        "DEMO_ACCOUNT_PASSWORD",
        [
            "/dashboard",
            "/dashboard/properties",
            "/dashboard/properties/new",
            "/dashboard/crm",
            "/dashboard/analytics",
            "/dashboard/agency",
            "/account",
            "/account/billing",
            "/favorites",
            "/saved-searches",
            "/notifications",
            "/messages",
            "/studio",
            "/vision",
        ],
    ),
    (
        "admin",
        "demo.admin@example.com",
        "DEMO_ADMIN_PASSWORD",
        [
            "/admin",
            "/admin/users",
            "/admin/moderation",
            "/admin/verification",
            "/admin/ai",
            "/admin/analytics",
            "/admin/reports",
            "/admin/billing",
            "/admin/jobs",
            "/admin/audit",
            "/admin/system",
            "/admin/settings",
            "/admin/webhooks",
        ],
    ),
]
VIEWS = {
    "1440": {"width": 1440, "height": 900},
    "1920": {"width": 1920, "height": 1080},
    "390": {"width": 390, "height": 844},
    "768": {"width": 768, "height": 1024},
}
REPORT: list[dict] = []


def context(browser: Browser, lang: str, theme: str, view: str):
    phone = view == "390"
    ctx = browser.new_context(
        viewport=VIEWS[view],
        device_scale_factor=2 if phone else 1,
        is_mobile=phone,
        has_touch=phone,
        locale="ar-IQ" if lang == "ar" else "en-US",
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
        )
        if phone
        else None,
        color_scheme=theme,
    )
    ctx.add_cookies(
        [
            {"name": "locale", "value": lang, "url": WEB},
            {"name": "theme", "value": theme, "url": WEB},
        ]
    )
    return ctx


def settle(page: Page, path: str) -> None:
    if path.startswith("/map") or path == "/":
        canvas = page.locator("[data-testid=map-canvas]")
        for _ in range(40):
            if canvas.count() == 0 or int(canvas.first.get_attribute("data-bubbles") or 0) > 0:
                break
            page.wait_for_timeout(500)
    previews = page.locator("[data-testid=map-preview]")
    for _ in range(30):  # quiet preview maps draw their basemap (up to 15 s)
        if previews.count() == 0 or all(
            previews.nth(i).get_attribute("data-ready") == "1" for i in range(previews.count())
        ):
            break
        page.wait_for_timeout(500)
    flight = page.locator("[data-testid=flight-map]")
    for _ in range(60):  # the drone-flight map: until every tile in view is drawn (30 s)
        if flight.count() == 0 or flight.first.get_attribute("data-ready") == "1":
            break
        page.wait_for_timeout(500)
    for _ in range(12):  # a preview with an arrival move: until it has landed
        if previews.count() == 0 or all(
            previews.nth(i).get_attribute("data-phase") in (None, "settled")
            for i in range(previews.count())
        ):
            break
        page.wait_for_timeout(250)
    # Lazy images only load when they near the viewport, and a full-page
    # screenshot does not scroll: walk the page so every image is requested,
    # then wait until each one has loaded and faded in (or failed).
    page.evaluate(
        """async () => {
          const step = Math.max(200, window.innerHeight * 0.8);
          for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
            window.scrollTo(0, y);
            await new Promise((r) => setTimeout(r, 120));
          }
          window.scrollTo(0, 0);
        }"""
    )
    for _ in range(40):
        # SafeImage keeps opacity-0 until its onLoad marks it loaded.
        pending = page.evaluate(
            "() => [...document.images].filter(i => !i.complete"
            " || (i.naturalWidth > 0 && i.classList.contains('opacity-0'))).length"
        )
        if pending == 0:
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(900)  # entrance motion and the image fade-in


def shoot(page: Page, name: str, path: str, tag: str) -> None:
    errors: list[str] = []
    failed: list[str] = []
    page.on("console", lambda m: errors.append(m.text[:240]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:240]}"))
    page.on(
        "requestfailed",
        lambda r: failed.append(f"{r.url.replace(WEB, '')[:120]} {r.failure}")
        if "_rsc=" not in r.url
        else None,
    )
    t0 = time.monotonic()
    status = None
    try:
        resp = page.goto(WEB + path, wait_until="load", timeout=90_000)
        status = resp.status if resp else None
        settle(page, path)
        # Against the configured viewport: on phones the layout viewport grows
        # to fit overflowing content, so innerWidth would hide the overflow.
        overflow = page.evaluate(
            "() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth,"
            " window.innerWidth)"
        ) - page.viewport_size["width"]
        culprits = None
        if overflow and overflow > 1:
            # The outermost elements that stick out of the viewport (either side).
            culprits = page.evaluate(
                """() => {
                  const vw = document.documentElement.clientWidth;
                  const out = [];
                  for (const el of document.body.querySelectorAll('*')) {
                    const r = el.getBoundingClientRect();
                    if (!r.width || (r.right <= vw + 1 && r.left >= -1)) continue;
                    if (el.parentElement && (() => { const p = el.parentElement.getBoundingClientRect();
                      return p.right > vw + 1 || p.left < -1; })()) continue;
                    const cls = (el.getAttribute('class') || '').split(/\\s+/).slice(0, 6).join('.');
                    out.push(`${el.tagName.toLowerCase()}.${cls} [${Math.round(r.left)}..${Math.round(r.right)}] ${(el.textContent || '').trim().slice(0, 40)}`);
                    if (out.length >= 5) break;
                  }
                  return out;
                }"""
            )
        height = page.evaluate("() => document.documentElement.scrollHeight")
        file = OUT / f"{tag}--{name}.jpg"
        clip_h = min(height, MAX_H) if FULL else page.viewport_size["height"]
        page.screenshot(
            path=str(file),
            type="jpeg",
            quality=72,
            full_page=True,
            clip={"x": 0, "y": 0, "width": page.viewport_size["width"], "height": clip_h},
        )
    except Exception as exc:  # recorded, the run continues
        errors.append(f"capture failed: {type(exc).__name__}: {str(exc)[:200]}")
        overflow = None
    previews_ready = None
    broken_images = None
    try:
        broken_images = page.evaluate(
            "() => [...document.images].filter(i => i.complete && i.naturalWidth === 0)"
            ".map(i => i.getAttribute('src')).slice(0, 5)"
        )
    except Exception:
        pass
    try:
        pv = page.locator("[data-testid=map-preview]")
        previews_ready = [pv.nth(i).get_attribute("data-ready") for i in range(pv.count())]
    except Exception:
        pass
    flight_map = None
    try:
        if page.locator("[data-testid=flight-map]").count():
            # Is the basemap actually drawn? Luminance spread of the map canvas
            # (a blank canvas has almost none), plus the map's own signals.
            flight_map = page.evaluate(
                """() => {
                  const box = document.querySelector('[data-testid=flight-map]');
                  const gl = box.querySelector('canvas');
                  const out = { ready: box.dataset.ready || null, error: box.dataset.error || null };
                  if (!gl) return out;
                  const c = document.createElement('canvas');
                  c.width = 160; c.height = 100;
                  const ctx = c.getContext('2d');
                  ctx.drawImage(gl, 0, 0, 160, 100);
                  const d = ctx.getImageData(0, 0, 160, 100).data;
                  let sum = 0, sq = 0, n = 0;
                  for (let i = 0; i < d.length; i += 4) {
                    const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
                    sum += l; sq += l * l; n++;
                  }
                  const mean = sum / n;
                  out.luminance_mean = Math.round(mean);
                  out.luminance_sd = Math.round(Math.sqrt(sq / n - mean * mean) * 10) / 10;
                  return out;
                }"""
            )
    except Exception as exc:
        flight_map = {"error": f"probe failed: {type(exc).__name__}"}
    REPORT.append(
        {
            "shot": f"{tag}--{name}",
            "flight_map": flight_map,
            "map_previews_ready": previews_ready,
            "broken_images": broken_images,
            "path": path,
            "status": status,
            "seconds": round(time.monotonic() - t0, 1),
            "overflow_px": overflow,
            "overflow_culprits": culprits if overflow and overflow > 1 else None,
            "console_errors": errors[:8],
            "failed_requests": failed[:8],
        }
    )


def listing_paths(browser: Browser, n: int) -> list[str]:
    """The first ``n`` listing pages on /properties (distinct ids)."""
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(WEB + "/properties", wait_until="load", timeout=90_000)
    hrefs = page.eval_on_selector_all(
        "a[href^='/properties/']", "els => els.map(e => e.getAttribute('href'))"
    )
    ctx.close()
    out: list[str] = []
    for h in hrefs:
        if re.fullmatch(r"/properties/[0-9a-f-]{36}", h or "") and h not in out:
            out.append(h)
    return out[:n]


def first_listing(browser: Browser) -> str | None:
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(WEB + "/properties", wait_until="load", timeout=90_000)
    hrefs = page.eval_on_selector_all(
        "a[href^='/properties/']", "els => els.map(e => e.getAttribute('href'))"
    )
    ctx.close()
    for h in hrefs:
        if re.fullmatch(r"/properties/[0-9a-f-]{36}", h or ""):
            return h
    return None


def sign_in(page: Page, email: str, password: str) -> bool:
    page.goto(WEB + "/login", wait_until="load", timeout=90_000)
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    page.locator("form button[type=submit]").click()
    try:
        page.wait_for_url(lambda u: "/login" not in u, timeout=45_000)
        return True
    except Exception:
        return False


def map_states(browser: Browser, lang: str, view: str, theme: str = "dark") -> None:
    """Interaction states on /map: layers panel, drawing, phone sheet, a selection."""
    tag = f"{lang}-{theme}-{view}"
    ctx = context(browser, lang, theme, view)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))
    states: dict[str, str] = {}
    try:
        page.goto(WEB + "/map", wait_until="load", timeout=90_000)
        settle(page, "/map")

        def snap(name: str) -> None:
            page.wait_for_timeout(700)
            page.screenshot(path=str(OUT / f"{tag}--map-{name}.jpg"), type="jpeg", quality=72)
            states[name] = "ok"

        canvas = page.locator("[data-testid=map-canvas]")
        box = canvas.bounding_box()
        # A selected listing: click each price tag position until a selection opens.
        if box:
            found = False
            # Click only in the open map, never on the docked results rail
            # (a click there opens a listing and ends the run).
            x0, x1 = box["x"], box["x"] + box["width"]
            rail = page.locator("section:has([data-testid=map-total])").first
            rb = rail.bounding_box() if rail.count() and view != "390" else None
            if rb:
                if rb["x"] - x0 < x1 - (rb["x"] + rb["width"]):
                    x0 = rb["x"] + rb["width"]
                else:
                    x1 = rb["x"]
            for fx in (0.35, 0.45, 0.5, 0.55, 0.62, 0.4, 0.58):
                for fy in (0.3, 0.38, 0.45, 0.52, 0.6):
                    page.mouse.click(x0 + (x1 - x0) * fx, box["y"] + box["height"] * fy)
                    page.wait_for_timeout(250)
                    if "/map" not in page.url:
                        page.go_back(wait_until="load")
                        settle(page, "/map")
                        continue
                    if page.locator("[data-testid=map-selection]").count():
                        found = True
                        break
                if found:
                    break
            if found:
                snap("selected")
                close = page.locator("[data-testid=map-selection] button").first
                if close.count():
                    close.click()
                page.wait_for_timeout(400)
            else:
                # Phones start zoomed out (groups, no tags): choose from the
                # list instead ("Show on map" selects and glides to it).
                handle = page.locator("section button[aria-expanded]").first
                if handle.count() and handle.is_visible():
                    handle.click()
                    page.wait_for_timeout(500)
                show = page.locator("[data-testid=show-on-map]").first
                if show.count() and show.is_visible():
                    show.click()
                    page.wait_for_timeout(1_300)
                if page.locator("[data-testid=map-selection]").count():
                    snap("selected")
                    close = page.locator("[data-testid=map-selection] button").first
                    if close.count():
                        close.click()
                    page.wait_for_timeout(400)
                else:
                    states["selected"] = "no tag hit"
        if view != "390":
            # List → map: hovering a result outlines its price tag.
            row = page.locator("section a[href^='/properties/']").first
            if row.count():
                row.hover()
                snap("list-hover")
                page.mouse.move(5, 5)
        if box:
            # Closer in: tags spread out; then 3D buildings with a pitched camera.
            page.mouse.move(x0 + (x1 - x0) * 0.62, box["y"] + box["height"] * 0.45)
            for _ in range(6 if view == "390" else 3):
                page.mouse.wheel(0, -320)
                page.wait_for_timeout(350)
            page.wait_for_timeout(900)
            snap("zoomed")
            three = page.locator("[data-testid=buildings-3d]")
            if three.count():
                three.click()
                page.wait_for_timeout(1_600)
                snap("3d")
                three.click()
                page.wait_for_timeout(1_200)
        layers = page.locator("[data-testid=map-layers] summary")
        if layers.count():
            layers.first.click()
            snap("layers")
            layers.first.click()
        if view == "390":
            handle = page.locator("section button[aria-expanded]").first
            if handle.count() and handle.is_visible():
                handle.click()
                snap("sheet-open")
                handle.click()
                page.wait_for_timeout(600)
            # Touch drag of the sheet (emulated touch through the DevTools
            # protocol — not a real device): up from peek, then back down.
            grip = page.locator("[data-testid=sheet-handle]")
            hb = grip.bounding_box() if grip.count() else None
            if hb:
                cdp = ctx.new_cdp_session(page)
                x, y = hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2

                def swipe(dy: float) -> str:
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
                    for i in range(1, 13):
                        cdp.send(
                            "Input.dispatchTouchEvent",
                            {"type": "touchMove", "touchPoints": [{"x": x, "y": y + dy * i / 12}]},
                        )
                        page.wait_for_timeout(16)
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                    page.wait_for_timeout(700)
                    return page.locator("[data-sheet]").first.get_attribute("data-sheet") or "?"

                up = swipe(-330)
                snap("sheet-dragged")
                hb2 = grip.bounding_box()
                if hb2:
                    x, y = hb2["x"] + hb2["width"] / 2, hb2["y"] + hb2["height"] / 2
                down = swipe(330)
                states["touch-drag (emulated)"] = f"peek->{up}->{down}"
        draw = page.locator("[data-testid=draw-area]")
        if draw.count() and box:
            draw.click()
            for dx, dy in ((-0.15, -0.12), (0.12, -0.1)):
                page.mouse.click(
                    box["x"] + box["width"] * (0.5 + dx), box["y"] + box["height"] * (0.5 + dy)
                )
                page.wait_for_timeout(300)
            snap("drawing")
    except Exception as exc:  # recorded, the run continues
        errors.append(f"map states failed: {type(exc).__name__}: {str(exc)[:200]}")
    REPORT.append({"shot": f"{tag}--map-states", "states": states, "console_errors": errors[:8]})
    ctx.close()


def hero_timeline(browser: Browser) -> None:
    """Reproduce the home hero map in real time: phase, tags placed, tags visible.

    Samples every 250 ms for 9 s after navigation in each theme, so a missing
    price tag can be told apart from a capture taken mid-animation.
    """
    for lang, theme in (("en", "dark"), ("en", "light"), ("ar", "dark"), ("ar", "light")):
        ctx = context(browser, lang, theme, "1440")
        page = ctx.new_page()
        samples: list[dict] = []
        try:
            t0 = time.monotonic()
            page.goto(WEB + "/", wait_until="load", timeout=90_000)
            for _ in range(36):
                state = page.evaluate(
                    """() => {
                      const el = document.querySelector('[data-testid=map-preview]');
                      if (!el) return null;
                      const tags = [...el.querySelectorAll('.map-tag')];
                      const vw = window.innerWidth, vh = window.innerHeight;
                      const seen = tags.filter((t) => {
                        const r = t.getBoundingClientRect();
                        const st = getComputedStyle(t.parentElement);
                        return st.visibility !== 'hidden' && parseFloat(getComputedStyle(t).opacity) > 0.5
                          && r.right > 0 && r.left < vw && r.bottom > 0 && r.top < vh;
                      }).length;
                      return {ready: el.dataset.ready, phase: el.dataset.phase || null,
                              total: el.dataset.tagsTotal || null, shown: el.dataset.tagsShown || null,
                              candidates: tags.length, visible: seen};
                    }"""
                )
                samples.append({"t": round(time.monotonic() - t0, 2), **(state or {})})
                page.wait_for_timeout(250)
            page.screenshot(path=str(OUT / f"{lang}-{theme}-1440--hero-9s.jpg"), type="jpeg", quality=72)
        except Exception as exc:  # recorded, the run continues
            samples.append({"error": f"{type(exc).__name__}: {str(exc)[:200]}"})
        REPORT.append({"shot": f"{lang}-{theme}-1440--hero-timeline", "hero_timeline": samples})
        ctx.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        hero_timeline(browser)
        listing = first_listing(browser)
        three = listing_paths(browser, 3)
        compare = (
            "/compare?ids=" + ",".join(h.rsplit("/", 1)[1] for h in three) if len(three) == 3 else None
        )
        resolved = {
            "listing": listing,
            "compare-3": compare,
            "flight": f"{listing}/flight" if listing else None,
        }
        pages = [(n, resolved.get(n, path)) for n, path in PUBLIC]
        pages = [(n, path) for n, path in pages if path]
        combos = [
            ("ar", "dark", "1440"),
            ("en", "dark", "1440"),
            ("ar", "dark", "390"),
            ("en", "dark", "390"),
            ("ar", "light", "1440"),
            ("en", "light", "390"),
            ("ar", "dark", "1920"),
        ]
        for lang, theme, view in combos:
            tag = f"{lang}-{theme}-{view}"
            subset = pages if theme == "dark" and view in ("1440", "390") else pages[:5]
            for name, path in subset:
                ctx = context(browser, lang, theme, view)
                page = ctx.new_page()
                shoot(page, name, path, tag)
                ctx.close()
        # The product pages in the other themes and on a tablet.
        key = {n: path for n, path in pages if n in ("listing", "compare-3", "market", "smart", "flight")}
        for lang, theme, view in (
            ("en", "light", "1440"),
            ("ar", "light", "390"),
            ("en", "dark", "768"),
        ):
            for name, path in key.items():
                ctx = context(browser, lang, theme, view)
                page = ctx.new_page()
                shoot(page, name, path, f"{lang}-{theme}-{view}")
                ctx.close()
        for lang, view, theme in (
            ("ar", "1440", "dark"),
            ("ar", "390", "dark"),
            ("en", "390", "dark"),
            ("en", "1440", "light"),
            ("ar", "390", "light"),
            ("en", "768", "dark"),
            ("ar", "768", "light"),
        ):
            map_states(browser, lang, view, theme)
        for who, email, env, paths in SIGNED_IN:
            password = os.environ.get(env)
            if not password:
                continue
            for view in ("1440", "390"):
                ctx = context(browser, "ar", "dark", view)
                page = ctx.new_page()
                if not sign_in(page, email, password):
                    REPORT.append({"shot": f"{who}-{view}", "console_errors": ["sign-in failed"]})
                    ctx.close()
                    continue
                for path in paths:
                    shoot(page, f"{who}{path.replace('/', '_')}", path, f"ar-dark-{view}")
                ctx.close()
        public = os.environ.get("PUBLIC_URL", "").rstrip("/")
        if public:
            # The preview URL itself, in a real browser (what a phone will load).
            global WEB
            local, WEB = WEB, public
            for view in ("390", "1440"):
                for name, path in (("public-home", "/"), ("public-map", "/map")):
                    ctx = context(browser, "ar", "dark", view)
                    page = ctx.new_page()
                    shoot(page, name, path, f"ar-dark-{view}")
                    ctx.close()
            WEB = local
        browser.close()
    (OUT / "report.json").write_text(json.dumps(REPORT, indent=1, ensure_ascii=False))
    bad = [r for r in REPORT if r.get("console_errors") or r.get("failed_requests") or (r.get("overflow_px") or 0) > 1]
    print(f"{len(REPORT)} shots; {len(bad)} with console errors, failed requests or overflow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
