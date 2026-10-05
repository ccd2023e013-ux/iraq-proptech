"""Real-browser check of the DEPLOYED site (Chromium via Playwright).

Verifies what HTTP checks cannot: the Arabic RTL page renders on a phone, the
language switch works, the MapLibre map actually draws tiles and shows
properties, the map list links to a property, the property photo loads and the
AI summary button produces a labelled answer, dark mode and the theme toggle
work, and a person can register, sign in, sign out and recover a password on
a phone (Arabic) and on a desktop (English). The account it creates uses the
same throw-away pattern as the API acceptance test (e2e-*@example.com).
Screenshots go to ./screenshots.

    WEB_URL=https://… python scripts/live/browser_check.py
"""

from __future__ import annotations

import io
import os
import statistics
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, Response, sync_playwright

WEB = os.environ["WEB_URL"].rstrip("/")
OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("  ✓ " if condition else "  ✗ ") + message, flush=True)
    if not condition:
        FAILURES.append(message)


def no_horizontal_scroll(page: Page) -> bool:
    # Compare with the device width, not innerWidth: mobile browsers zoom out
    # (and grow innerWidth) when content is wider than the screen.
    width = (page.viewport_size or {"width": 0})["width"]
    return page.evaluate(f"document.documentElement.scrollWidth <= {width} + 1")


INVALID_CREDENTIALS_AR = "البريد الإلكتروني أو كلمة المرور غير صحيحة."
INVALID_CREDENTIALS_EN = "Incorrect email or password."


def future_iraq(browser) -> None:
    """Stage 5: Future Iraq page cites sources; the map layer shows projects."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
    page = ctx.new_page()
    page.goto(WEB + "/future", wait_until="load", timeout=120_000)
    projects = page.locator("[data-testid=future-project]")
    count = projects.count()
    check(count > 0, f"Future Iraq lists published projects ({count})")
    if count:
        links = projects.first.locator('a[href^="https://"]')
        check(links.count() > 0, "each project links to its published source")
    page.screenshot(path=str(OUT / "future.png"), full_page=True)
    page.goto(WEB + "/map?bbox=47.80,29.80,48.60,30.20&layer=future", wait_until="load")
    canvas = page.locator("[data-testid=map-canvas]")
    shown = 0
    for _ in range(40):
        shown = int(canvas.get_attribute("data-projects") or 0)
        if shown > 0:
            break
        page.wait_for_timeout(1_000)
    check(shown > 0, f"Future Iraq map layer shows projects ({shown})")
    page.screenshot(path=str(OUT / "future-map.png"))
    ctx.close()


def themes(browser) -> None:
    """Dark mode follows the system by default; the toggle can force light."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, color_scheme="dark")
    page = ctx.new_page()
    page.goto(WEB + "/", wait_until="load", timeout=120_000)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    rgb = [int(x) for x in bg[bg.index("(") + 1 : bg.index(")")].split(",")[:3]]
    check(sum(rgb) / 3 < 60, f"system dark mode renders a dark page ({bg})")
    page.screenshot(path=str(OUT / "home-dark.png"))
    toggle = page.locator("header [data-theme-choice]").first
    before = page.get_attribute("html", "data-theme")
    toggle.click()
    page.wait_for_timeout(300)
    after = page.get_attribute("html", "data-theme")
    check(before != after, f"theme toggle changes the theme ({before} → {after})")
    ctx.close()


def auth_flow(browser, *, phone: bool, locale: str) -> None:
    """register → wrong password → sign in → guarded redirect → sign out → recovery."""
    tag = f"{'phone' if phone else 'desktop'}-{locale}"
    opts = (
        {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
        if phone
        else {"viewport": {"width": 1366, "height": 900}}
    )
    ctx = browser.new_context(locale="ar-IQ" if locale == "ar" else "en-US", **opts)
    page = ctx.new_page()
    def on_auth(r: Response) -> None:
        if "/api/v1/auth/login" in r.url or "/api/v1/auth/register" in r.url:
            redacted = [
                h["value"].split("=", 1)[0] + "=…;" + h["value"].split(";", 1)[-1]
                for h in r.headers_array()
                if h["name"].lower() == "set-cookie"
            ]
            print(f"  [{tag}] {r.status} {r.url[-24:]} set-cookie: {redacted}", flush=True)

    page.on("response", on_auth)
    email = f"e2e-browser-{int(time.time())}-{tag}@example.com"
    password = f"Live-{int(time.time())}-Check!"

    # Pages exist (they were 404 before 2.0).
    for path in ("/login", "/register", "/forgot-password", "/reset-password", "/verify-email"):
        r = page.goto(WEB + path, wait_until="load", timeout=120_000)
        check(bool(r and r.status == 200), f"[{tag}] {path} renders ({r.status if r else '-'})")
    check(page.get_attribute("html", "lang") == locale, f"[{tag}] page language is {locale}")

    # Register: client validation first, then a real account.
    page.goto(WEB + "/register", wait_until="load", timeout=120_000)
    if phone:
        check(no_horizontal_scroll(page), f"[{tag}] register fits the phone width")
    page.locator("form button[type=submit]").click()
    check(
        page.locator("form [role=alert]").count() >= 3,
        f"[{tag}] empty registration shows field errors",
    )
    page.fill("input[name=full_name]", "Live Browser Check")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    page.screenshot(path=str(OUT / f"register-{tag}.png"), full_page=True)
    with page.expect_response(lambda r: "/api/v1/auth/register" in r.url, timeout=90_000) as reg:
        page.locator("form button[type=submit]").click()
    check(reg.value.status == 201, f"[{tag}] registration accepted ({reg.value.status})")
    # On success the form is replaced by the confirmation.
    page.wait_for_selector("main form", state="detached", timeout=30_000)
    check(True, f"[{tag}] registration confirmation shown")
    page.screenshot(path=str(OUT / f"registered-{tag}.png"), full_page=True)

    # Wrong password → clear, localized error.
    page.goto(WEB + "/login?next=/favorites", wait_until="load", timeout=120_000)
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password + "x")
    with page.expect_response(lambda r: "/api/v1/auth/login" in r.url, timeout=90_000) as bad:
        page.locator("form button[type=submit]").click()
    check(bad.value.status == 401, f"[{tag}] wrong password rejected ({bad.value.status})")
    alert = page.locator("form > [role=alert]").first
    alert.wait_for(timeout=60_000)
    expected = INVALID_CREDENTIALS_AR if locale == "ar" else INVALID_CREDENTIALS_EN
    check(expected in alert.inner_text(), f"[{tag}] wrong password shows a clear error")

    # Correct password → back to the guarded page that asked for it.
    page.fill("input[name=password]", password)
    with page.expect_response(lambda r: "/api/v1/auth/login" in r.url, timeout=90_000) as good:
        page.locator("form button[type=submit]").click()
    check(good.value.status == 200, f"[{tag}] correct password accepted ({good.value.status})")
    page.wait_for_url(lambda u: "/favorites" in u and "/login" not in u, timeout=60_000)
    check(True, f"[{tag}] sign-in returns to the requested page (/favorites)")
    cookies = {c["name"]: c for c in ctx.cookies()}
    print(
        f"  [{tag}] cookies after sign-in: "
        + ", ".join(
            f"{n}(len={len(c['value'])},httpOnly={c['httpOnly']},secure={c['secure']},"
            f"domain={c['domain']},expires={int(c['expires'])})"
            for n, c in cookies.items()
        ),
        flush=True,
    )
    me_status = page.evaluate(
        "fetch('/api/v1/auth/me', {credentials: 'same-origin'}).then(r => r.status)"
    )
    print(f"  [{tag}] browser GET /api/v1/auth/me → {me_status}; url={page.url}", flush=True)
    session = cookies.get("access_token", {})
    check(
        bool(session.get("httpOnly")) and bool(session.get("secure")),
        f"[{tag}] session cookie is HttpOnly + Secure",
    )
    page.goto(WEB + "/login", wait_until="load", timeout=120_000)
    check("/login" not in page.url, f"[{tag}] signed-in visit to /login redirects ({page.url})")
    page.screenshot(path=str(OUT / f"signed-in-{tag}.png"))

    # Sign out from the user menu.
    page.locator("header button[aria-haspopup=menu]").click()
    page.locator("header [role=menuitem]").last.click()
    page.wait_for_selector('header a[href="/register"]', timeout=60_000)
    check(True, f"[{tag}] sign-out returns to the signed-out header")
    page.goto(WEB + "/favorites", wait_until="load", timeout=120_000)
    check("/login" in page.url, f"[{tag}] guarded page needs sign-in after sign-out")

    # Recovery: either a working form or an honest "email unavailable" notice.
    page.goto(WEB + "/forgot-password", wait_until="load", timeout=120_000)
    has_form = page.locator("form input[name=email]").count() == 1
    has_notice = page.locator("main [role=status]").count() >= 1
    check(has_form or has_notice, f"[{tag}] password recovery is usable or honestly unavailable")
    page.screenshot(path=str(OUT / f"forgot-{tag}.png"))
    ctx.close()


def map_v2(browser) -> None:
    """Stage 3: price bubbles, places layer, draw-area search (Basra viewport)."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
    page = ctx.new_page()
    warnings: list[str] = []
    page.on("console", lambda m: warnings.append(m.text) if "[map]" in m.text else None)
    seen: list[str] = []
    page.on(
        "response",
        lambda r: seen.append(f"{r.status} {r.url.split('/api/v1/')[-1][:90]}")
        if "/api/v1/pois" in r.url or "/api/v1/map/" in r.url
        else None,
    )
    page.goto(WEB + "/map?bbox=47.70,30.40,47.92,30.62", wait_until="load", timeout=120_000)
    canvas = page.locator("[data-testid=map-canvas]")
    page.wait_for_selector("[data-testid=map-canvas][data-bubbles]", timeout=60_000)
    page.wait_for_timeout(3_000)
    bubbles = int(canvas.get_attribute("data-bubbles") or 0)
    clusters = int(canvas.get_attribute("data-clusters") or 0)
    zoom = canvas.get_attribute("data-zoom")
    check(bubbles > 0, f"Basra shows price bubbles ({bubbles} bubbles, {clusters} clusters, z{zoom})")
    page.screenshot(path=str(OUT / "map-bubbles.png"))

    # Places layer: schools in Basra (OSM or demo).
    page.locator("[data-testid=map-layers] summary").click()
    page.locator("[data-place=SCHOOL]").click()
    pois_ok = False
    for _ in range(40):  # attribute polling: the site's CSP forbids eval-based waits
        if int(canvas.get_attribute("data-pois") or 0) > 0:
            pois_ok = True
            break
        page.wait_for_timeout(1_000)
    check(pois_ok, f"places layer toggles on ({canvas.get_attribute('data-pois')} places)")
    print(f"  map requests: {seen[-6:]}", flush=True)
    print(f"::notice title=map diagnostics::warnings={warnings[:5]} zoom={zoom}", flush=True)
    page.screenshot(path=str(OUT / "map-places.png"))
    page.locator("[data-testid=map-layers] summary").click()

    # Draw a triangle around the centre and search inside it.
    before = page.locator("[data-testid=map-total]").inner_text()
    page.locator("[data-testid=draw-area]").click()
    box = canvas.bounding_box()
    assert box is not None
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for dx, dy in ((-120, -90), (130, -80), (0, 120)):
        page.mouse.click(cx + dx, cy + dy)
        page.wait_for_timeout(700)
    finish = page.locator("[data-testid=finish-area]")
    check(finish.is_enabled(), "three clicks add three points to the drawn area")
    finish.click()
    page.wait_for_url(lambda u: "polygon=" in u, timeout=30_000, wait_until="commit")
    page.wait_for_load_state("load")
    page.wait_for_timeout(2_500)
    after = page.locator("[data-testid=map-total]").inner_text()
    check("polygon=" in page.url, f"draw-area search filters by polygon ({before!r} → {after!r})")
    page.screenshot(path=str(OUT / "map-drawn.png"))
    ctx.close()

    # "Properties near you" (homepage) and "Near me" (map) with a Basra location.
    ctx = browser.new_context(
        viewport={"width": 1366, "height": 900},
        locale="en-US",
        permissions=["geolocation"],
        geolocation={"latitude": 30.508, "longitude": 47.783},
    )
    page = ctx.new_page()
    page.goto(WEB + "/", wait_until="load", timeout=120_000)
    page.locator("[data-testid=near-you]").click()
    near = page.locator('section[aria-labelledby=near-heading] a[href^="/properties/"]')
    try:
        near.first.wait_for(timeout=60_000)
        found = near.count()
    except Exception:
        found = 0
    check(found > 0, f"homepage 'near you' lists nearby properties ({found})")
    page.goto(WEB + "/map", wait_until="load", timeout=120_000)
    page.get_by_role("button", name="Near me").click()
    page.wait_for_url(lambda u: "near_lat=" in u, timeout=30_000, wait_until="commit")
    check("radius_km=3" in page.url, "map 'near me' runs a 3 km radius search")
    ctx.close()


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )

        if os.environ.get("BROWSER_ONLY") == "map":
            map_v2(browser)
            future_iraq(browser)
            browser.close()
            print("MAP-ONLY RESULT: " + ("OK" if not FAILURES else "; ".join(FAILURES)))
            return 1 if FAILURES else 0
        if os.environ.get("BROWSER_ONLY") == "auth":
            themes(browser)
            auth_flow(browser, phone=True, locale="ar")
            auth_flow(browser, phone=False, locale="en")
            browser.close()
            print("AUTH-ONLY RESULT: " + ("OK" if not FAILURES else "; ".join(FAILURES)))
            return 1 if FAILURES else 0

        # 1. Phone, Arabic default.
        phone = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="ar-IQ",
        )
        page = phone.new_page()
        page.goto(WEB + "/", wait_until="load", timeout=120_000)
        check(page.get_attribute("html", "dir") == "rtl", "home page is RTL")
        check(page.get_attribute("html", "lang") == "ar", "home page is Arabic")
        check(no_horizontal_scroll(page), "no horizontal scrolling on a 390px phone")
        page.screenshot(path=str(OUT / "home-ar-phone.png"), full_page=True)
        phone.close()

        # 2. Desktop: language switch.
        desktop = browser.new_context(viewport={"width": 1366, "height": 900}, locale="ar-IQ")
        page = desktop.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(WEB + "/", wait_until="load", timeout=120_000)
        page.locator('header button[lang="en"]').first.click()
        # Selector waits, not wait_for_function: the site's CSP forbids eval.
        page.wait_for_selector('html[lang="en"]', state="attached", timeout=30_000)
        check(page.get_attribute("html", "dir") == "ltr", "English switch → LTR")
        page.screenshot(path=str(OUT / "home-en.png"))
        page.locator('header button[lang="ar"]').first.click()
        page.wait_for_selector('html[lang="ar"]', state="attached", timeout=30_000)

        # 3. Map: tiles drawn, properties returned, list ↔ map, click through.
        tiles: list[int] = []
        failed_urls: list[str] = []
        features: list[int] = []

        def on_response(r: Response) -> None:
            if r.status >= 400:
                failed_urls.append(f"{r.status} {r.url[:120]}")
            if "openfreemap.org" in r.url and r.status == 200:
                tiles.append(r.status)
            if "/api/v1/map/properties" in r.url and r.status == 200:
                try:
                    features.append(len(r.json().get("features", [])))
                except Exception:
                    features.append(-1)

        page.on("response", on_response)
        page.goto(WEB + "/map", wait_until="load", timeout=120_000)
        page.wait_for_selector("[data-testid=map-canvas] canvas", timeout=60_000)
        page.wait_for_timeout(8_000)  # let tiles and the property layer draw
        info = page.evaluate(
            """() => {
              const el = document.querySelector('[data-testid=map-canvas]');
              const chain = [];
              for (let n = el; n && chain.length < 6; n = n.parentElement) {
                const r = n.getBoundingClientRect(), cs = getComputedStyle(n);
                chain.push(`${n.tagName}.${(n.className || '').toString().slice(0, 40)} `
                  + `${Math.round(r.width)}x${Math.round(r.height)} `
                  + `${cs.display}/${cs.visibility}`);
              }
              const alert = document.querySelector('[role=alert]');
              return {chain, alert: alert ? alert.textContent : null,
                      width: window.innerWidth,
                      canvases: document.querySelectorAll('canvas').length};
            }"""
        )
        print(f"  map element diagnostics: {info}", flush=True)
        page.screenshot(path=str(OUT / "map-page.png"), full_page=True)
        box = page.locator("[data-testid=map-canvas]").bounding_box()
        check(bool(box and box["width"] > 100 and box["height"] > 100), f"map has a size ({box})")
        if not box or box["width"] < 10 or box["height"] < 10:
            raise SystemExit(f"BROWSER CHECK FAILED: map element not visible: {info}")
        shot = page.screenshot(clip=box)
        (OUT / "map.png").write_bytes(shot)
        gray = Image.open(io.BytesIO(shot)).convert("L").resize((200, 120))
        spread = statistics.pstdev(gray.getdata())
        check(len(tiles) > 0, f"map tiles loaded ({len(tiles)} tile responses)")
        check(spread > 8, f"map canvas is drawn, not blank (pixel spread {spread:.1f})")
        check(bool(features) and max(features) > 0, f"map received properties ({features[-3:]})")
        cards = page.locator('a[href^="/properties/"]')
        check(cards.count() > 0, f"map list shows {cards.count()} properties")
        if cards.count() > 0:
            cards.first.hover()
            href = cards.first.get_attribute("href")
            cards.first.click()
            page.wait_for_url(f"**{href}", timeout=60_000)
            check(True, "map list item opens the property page")

        # 4. Property page: photo, AI summary.
        page.wait_for_load_state("load")
        img = page.locator("img[src*='/api/v1/media/']").first
        img.wait_for(timeout=30_000)
        loaded = page.evaluate("(el) => el.complete && el.naturalWidth > 0", img.element_handle())
        check(bool(loaded), "property photo loaded")
        page.get_by_role("button", name="لخّص هذا العقار").click()
        summary = page.locator("[data-testid=ai-summary]")
        summary.wait_for(timeout=60_000)
        provider = summary.locator("[data-ai-provider]").first.get_attribute("data-ai-provider")
        check(provider == "mock", f"AI summary shown and labelled ({provider})")
        check(len(summary.inner_text()) > 40, "AI summary has content")
        # Stage 4: property intelligence — typed statements and the buyer assistant.
        page.locator("[data-testid=intelligence-analyze]").click()
        report = page.locator("[data-testid=intelligence-report]")
        report.wait_for(timeout=90_000)
        kinds = {
            k
            for k in report.locator("[data-kind]").evaluate_all("els => els.map(e => e.dataset.kind)")
        }
        check(
            {"FACT", "ESTIMATE", "AI_INTERPRETATION"} <= kinds,
            f"intelligence report labels every statement ({sorted(kinds)})",
        )
        page.fill("#intel-question", "كم سعر هذا العقار؟")
        page.locator("[data-testid=intelligence-ask]").click()
        answers = page.locator("[data-testid=intelligence-answers] [data-kind=AI_INTERPRETATION]")
        answers.first.wait_for(timeout=60_000)
        check(answers.count() >= 1, "buyer assistant answers, labelled as AI interpretation")
        page.screenshot(path=str(OUT / "property.png"), full_page=True)

        # 5. Stage 1/2 (2.0): themes and the authentication journey; Stage 3 map.
        map_v2(browser)
        future_iraq(browser)
        themes(browser)
        auth_flow(browser, phone=True, locale="ar")
        auth_flow(browser, phone=False, locale="en")

        csp = [e for e in errors if "Content Security Policy" in e]
        check(not csp, f"no CSP violations in the console ({csp[:2]})")
        if errors:
            print("  console errors (informational):", errors[:5])
        if failed_urls:
            print("  failed requests (informational):", sorted(set(failed_urls))[:10])
        browser.close()

    print(
        f"::notice title=live browser summary::{'OK' if not FAILURES else 'FAILED'}: "
        "RTL+mobile, EN switch, map tiles/properties/list, photo, AI summary, "
        "dark mode, auth journey (phone AR + desktop EN), map bubbles/places/draw"
    )
    if FAILURES:
        print("BROWSER CHECK FAILED: " + "; ".join(FAILURES))
        return 1
    print("BROWSER CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
