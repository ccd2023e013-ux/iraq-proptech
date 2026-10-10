"""MapLibre checks in a real browser against the CI Docker stack (pre-merge).

Complements ``scripts/live/browser_check.py`` (BROWSER_ONLY=map: bubbles,
places, drawing, near me, Future Iraq), which otherwise only ever runs against
production. Added with the MapLibre 6 upgrade, whose risks are rendering, the
worker (ESM build, loaded from a URL under the site's CSP), attribution
sanitising (GHSA-jrc7-96c5-q579) and Arabic text without the RTL plugin.

For each of 8 states — Arabic (RTL) and English, light and dark, desktop and
phone — the /map page must:
  * render the MapLibre canvas and draw price bubbles for Basra;
  * use the page direction of its language;
  * show an attribution control crediting OpenStreetMap that contains no event
    handler attributes, scripts or frames;
  * fit the viewport (no horizontal scroll);
and the whole run must log no page errors, no CSP violations and no worker
errors. A theme switch re-runs setStyle and must redraw the overlays.

    WEB_URL=http://localhost:3000 python scripts/ci/maplibre_check.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

WEB = os.environ.get("WEB_URL", "http://localhost:3000").rstrip("/")
BASRA = "/map?bbox=47.70,30.40,47.92,30.62"
OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)
FAILURES: list[str] = []


def check(condition: bool, message: str) -> bool:
    print(("  ✓ " if condition else "  ✗ ") + message, flush=True)
    if not condition:
        FAILURES.append(message)
    return condition


def poll_bubbles(page: Page, seconds: int = 60) -> int:
    canvas = page.locator("[data-testid=map-canvas]")
    bubbles = 0
    for _ in range(seconds):  # attribute polling: the site's CSP forbids eval-based waits
        bubbles = int(canvas.get_attribute("data-bubbles") or 0)
        if bubbles > 0:
            break
        page.wait_for_timeout(1_000)
    return bubbles


def no_horizontal_scroll(page: Page) -> bool:
    return bool(
        page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    )


def attribution_report(page: Page) -> dict:
    """Text and any dangerous markup inside MapLibre's attribution control."""
    return page.evaluate(
        """() => {
          const box = document.querySelector('.maplibregl-ctrl-attrib');
          if (!box) return {present: false};
          const all = [box, ...box.querySelectorAll('*')];
          const handlers = all.flatMap(el =>
            [...el.attributes]
              .filter(a => /^on/i.test(a.name))
              .map(a => el.tagName + '[' + a.name + ']'));
          const active = box.querySelectorAll('script, iframe, object, embed').length;
          return {present: true, text: box.textContent || '', handlers, active};
        }"""
    )


def state(browser: Browser, *, lang: str, scheme: str, phone: bool, errors: list[str]) -> dict:
    tag = f"{lang}-{scheme}-{'390' if phone else '1440'}"
    viewport = {"width": 390, "height": 844} if phone else {"width": 1440, "height": 900}
    ctx = browser.new_context(
        viewport=viewport,
        is_mobile=phone,
        has_touch=phone,
        color_scheme=scheme,
        locale="ar-IQ" if lang == "ar" else "en-US",
    )
    # The site defaults to dark; the theme cookie is what selects light or dark
    # (and therefore which basemap style MapLibre loads).
    ctx.add_cookies(
        [
            {"name": "locale", "value": lang, "url": WEB},
            {"name": "theme", "value": scheme, "url": WEB},
        ]
    )
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))
    page.on(
        "console",
        lambda m: (
            errors.append(f"[{tag}] console {m.type}: {m.text[:200]}")
            if m.type == "error" or "[map]" in m.text
            else None
        ),
    )
    page.goto(WEB + BASRA, wait_until="load", timeout=120_000)
    page.wait_for_selector("[data-testid=map-canvas] canvas.maplibregl-canvas", timeout=60_000)
    bubbles = poll_bubbles(page)
    ok = check(bubbles > 0, f"[{tag}] MapLibre canvas draws Basra price bubbles ({bubbles})")
    ok &= check(page.get_attribute("html", "data-theme") == scheme, f"[{tag}] theme is {scheme}")
    want_dir = "rtl" if lang == "ar" else "ltr"
    ok &= check(
        page.get_attribute("html", "dir") == want_dir
        and page.get_attribute("html", "lang") == lang,
        f"[{tag}] page is {lang}/{want_dir}",
    )
    attribution = attribution_report(page)
    ok &= check(
        attribution.get("present") and "OpenStreetMap" in attribution.get("text", ""),
        f"[{tag}] attribution control credits OpenStreetMap",
    )
    ok &= check(
        attribution.get("present")
        and not attribution.get("handlers")
        and attribution.get("active") == 0,
        f"[{tag}] attribution has no event handlers or active content "
        f"({attribution.get('handlers')}, {attribution.get('active')})",
    )
    ok &= check(no_horizontal_scroll(page), f"[{tag}] no horizontal overflow")
    shot = OUT / f"maplibre-{tag}.png"
    page.screenshot(path=str(shot))
    ctx.close()
    return {
        "state": tag,
        "url": WEB + BASRA,
        "bubbles": bubbles,
        "screenshot": shot.name,
        "passed": bool(ok),
    }


def theme_switch(browser: Browser, errors: list[str]) -> None:
    """Switching the site theme swaps the basemap (setStyle); overlays must return."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    ctx.add_cookies([{"name": "theme", "value": "light", "url": WEB}])
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"[theme] pageerror: {e}"))
    page.goto(WEB + BASRA, wait_until="load", timeout=120_000)
    check(page.get_attribute("html", "data-theme") == "light", "[theme] starts light")
    check(poll_bubbles(page) > 0, "[theme] bubbles before the switch")
    canvas = page.locator("[data-testid=map-canvas]")
    canvas.evaluate("el => { el.dataset.bubbles = ''; }")  # force a fresh count
    page.evaluate("() => { document.documentElement.dataset.theme = 'dark'; }")
    after = poll_bubbles(page)
    check(after > 0, f"[theme] bubbles redrawn after setStyle to the dark basemap ({after})")
    page.screenshot(path=str(OUT / "maplibre-theme-switched.png"))
    ctx.close()


def main() -> int:
    errors: list[str] = []
    ledger: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        for lang in ("ar", "en"):
            for scheme in ("light", "dark"):
                for phone in (False, True):
                    ledger.append(
                        state(browser, lang=lang, scheme=scheme, phone=phone, errors=errors)
                    )
        theme_switch(browser, errors)
        browser.close()

    csp = [e for e in errors if "Content Security Policy" in e or "Refused to" in e]
    worker = [e for e in errors if "worker" in e.lower()]
    page_errors = [e for e in errors if "pageerror" in e]
    check(not csp, f"no CSP violations ({csp[:2]})")
    check(not worker, f"no worker errors ({worker[:2]})")
    check(not page_errors, f"no uncaught page errors ({page_errors[:2]})")
    if errors:
        print("  console (informational):", errors[:8], flush=True)
    check(
        len(ledger) == 8 and len({e["state"] for e in ledger}) == 8,
        f"all 8 MapLibre states visited ({len(ledger)})",
    )
    (OUT / "maplibre-states.json").write_text(
        json.dumps(
            {"states": len(ledger), "passed": sum(e["passed"] for e in ledger), "ledger": ledger},
            indent=2,
        )
    )
    print(
        "MAPLIBRE CHECK " + ("OK" if not FAILURES else "FAILED: " + "; ".join(FAILURES)), flush=True
    )
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
