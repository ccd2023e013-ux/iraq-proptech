"""Real-browser check of the DEPLOYED site (Chromium via Playwright).

Verifies what HTTP checks cannot: the Arabic RTL page renders on a phone, the
language switch works, the MapLibre map actually draws tiles and shows
properties, the map list links to a property, the property photo loads and the
AI summary button produces a labelled answer. Screenshots go to ./screenshots.

    WEB_URL=https://… python scripts/live/browser_check.py
"""

from __future__ import annotations

import io
import os
import statistics
import sys
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
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )

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
        page.screenshot(path=str(OUT / "property.png"), full_page=True)

        csp = [e for e in errors if "Content Security Policy" in e]
        check(not csp, f"no CSP violations in the console ({csp[:2]})")
        if errors:
            print("  console errors (informational):", errors[:5])
        if failed_urls:
            print("  failed requests (informational):", sorted(set(failed_urls))[:10])
        browser.close()

    print(
        f"::notice title=live browser summary::{'OK' if not FAILURES else 'FAILED'}: "
        f"RTL+mobile, EN switch, map tiles/properties/list, photo, AI summary"
    )
    if FAILURES:
        print("BROWSER CHECK FAILED: " + "; ".join(FAILURES))
        return 1
    print("BROWSER CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
