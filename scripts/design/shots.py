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
    ("notfound", "/this-page-does-not-exist"),
]
SIGNED_IN = [
    ("agent", "demo.agent@example.com", "DEMO_ACCOUNT_PASSWORD", ["/dashboard", "/dashboard/properties", "/account"]),
    ("admin", "demo.admin@example.com", "DEMO_ADMIN_PASSWORD", ["/admin", "/admin/users"]),
]
VIEWS = {
    "1440": {"width": 1440, "height": 900},
    "1920": {"width": 1920, "height": 1080},
    "390": {"width": 390, "height": 844},
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
    page.wait_for_timeout(1_200)  # entrance motion and image decode


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
        overflow = page.evaluate(
            "() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth,"
            " document.querySelector('main') ? document.querySelector('main').scrollWidth : 0)"
            " - window.innerWidth"
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
    try:
        pv = page.locator("[data-testid=map-preview]")
        previews_ready = [pv.nth(i).get_attribute("data-ready") for i in range(pv.count())]
    except Exception:
        pass
    REPORT.append(
        {
            "shot": f"{tag}--{name}",
            "map_previews_ready": previews_ready,
            "path": path,
            "status": status,
            "seconds": round(time.monotonic() - t0, 1),
            "overflow_px": overflow,
            "console_errors": errors[:8],
            "failed_requests": failed[:8],
        }
    )


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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        listing = first_listing(browser)
        pages = [(n, listing if n == "listing" else path) for n, path in PUBLIC]
        pages = [(n, path) for n, path in pages if path]
        combos = [
            ("ar", "dark", "1440"),
            ("en", "dark", "1440"),
            ("ar", "dark", "390"),
            ("en", "dark", "390"),
            ("ar", "light", "1440"),
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
