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

# Installed before any page script runs (via CDP, so the site's CSP does not
# apply): logs what an uncaught error or unhandled rejection really was, since
# Playwright reports non-Error reasons only as "Error" without a stack.
DIAGNOSTIC_HOOK = """
(() => {
  const what = (v) => {
    try {
      if (v instanceof Error) {
        const top = (v.stack || '').split('\\n').slice(0, 4).join(' | ');
        return `${v.name}: ${v.message} @ ${top}`;
      }
      if (v instanceof Event) {
        const t = v.target || {};
        return `Event(${v.type}) target=${t.constructor && t.constructor.name} ` +
          `src=${t.src || t.url || t.href || ''} msg=${v.message || ''}`;
      }
      return `${Object.prototype.toString.call(v)} ${JSON.stringify(v)}`.slice(0, 300);
    } catch (e) { return String(v); }
  };
  addEventListener('unhandledrejection',
    (e) => console.error('[diag] unhandledrejection ' + what(e.reason)));
  addEventListener('error', (e) => console.error('[diag] error ' + what(e.error || e) +
    ` file=${e.filename || ''}:${e.lineno || ''}:${e.colno || ''}`), true);
})();
"""


def describe(error: Exception) -> str:
    """Name, message and the top of the stack of an uncaught page error."""
    name = getattr(error, "name", "") or type(error).__name__
    message = getattr(error, "message", "") or str(error)
    stack = (getattr(error, "stack", "") or "").replace("\n", " | ")
    return f"{name}: {message!r} stack: {stack[:700]}"


def check(condition: bool, message: str) -> bool:
    print(("  ✓ " if condition else "  ✗ ") + message, flush=True)
    if not condition:
        FAILURES.append(message)
    return condition


def poll_bubbles(page: Page, seconds: int = 60) -> int:
    return poll_listings(page, seconds)[0]


def poll_listings(page: Page, seconds: int = 60) -> tuple[int, int]:
    """(price bubbles, clusters) the map reports once listings are drawn."""
    canvas = page.locator("[data-testid=map-canvas]")
    bubbles = clusters = 0
    for _ in range(seconds):  # attribute polling: the site's CSP forbids eval-based waits
        bubbles = int(canvas.get_attribute("data-bubbles") or 0)
        clusters = int(canvas.get_attribute("data-clusters") or 0)
        if bubbles > 0 or clusters > 0:
            break
        page.wait_for_timeout(1_000)
    return bubbles, clusters


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
    ctx.add_init_script(DIAGNOSTIC_HOOK)
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {describe(e)}"))
    page.on(
        "console",
        lambda m: (
            errors.append(
                f"[{tag}] console {m.type}: {m.text[: 2000 if '[diag]' in m.text else 300]}"
            )
            if m.type in ("error", "warning") or "[map]" in m.text
            else None
        ),
    )
    # Diagnostics: what the map fetched (style, tiles, glyphs, worker) and what failed.
    fetched: list[str] = []
    worker_loads: list[dict] = []
    page.on(
        "response",
        lambda r: (
            worker_loads.append(
                {
                    "url": r.url,
                    "status": r.status,
                    "type": r.headers.get("content-type", ""),
                    "same_origin": r.url.startswith(WEB + "/"),
                }
            )
            if "maplibre-gl-worker" in r.url
            else None
        ),
    )
    page.on(
        "response",
        lambda r: (
            fetched.append(f"{r.status} {r.request.resource_type} {r.url[:110]}")
            if "openfreemap" in r.url or "worker" in r.url.lower() or r.status >= 400
            else None
        ),
    )
    page.on(
        "requestfailed",
        lambda r: errors.append(f"[{tag}] requestfailed {r.url[:120]} {r.failure}"),
    )
    page.goto(WEB + BASRA, wait_until="load", timeout=120_000)
    canvas_ok = False
    for _ in range(60):
        if page.locator("[data-testid=map-canvas] canvas.maplibregl-canvas").count() > 0:
            canvas_ok = True
            break
        page.wait_for_timeout(1_000)
    check(canvas_ok, f"[{tag}] MapLibre created its canvas")
    bubbles, clusters = poll_listings(page) if canvas_ok else (0, 0)
    if phone:
        # On a 390 px screen Basra fits at a lower zoom, where listings are
        # (correctly) clustered; what matters is that listings are drawn.
        drawn = bubbles + clusters > 0
        what = f"listings ({bubbles} bubbles, {clusters} clusters)"
    else:
        drawn = bubbles > 0
        what = f"price bubbles ({bubbles})"
    ok = canvas_ok and check(drawn, f"[{tag}] MapLibre canvas draws Basra {what}")
    workers = [w for w in worker_loads if "/maplibre/maplibre-gl-worker-" in w["url"]]
    ok &= check(
        bool(workers)
        and all(
            w["same_origin"] and w["status"] == 200 and "javascript" in w["type"] for w in workers
        ),
        f"[{tag}] MapLibre worker served by the site itself (same origin, 200, JavaScript): "
        f"{[(w['status'], w['type']) for w in workers][:1]}",
    )
    if not ok:
        state_attrs = page.locator("[data-testid=map-canvas]").evaluate(
            "el => ({cls: el.className, data: {...el.dataset}, text: el.innerText.slice(0, 200)})"
        )
        print(f"  [{tag}] map element: {state_attrs}", flush=True)
        print(f"  [{tag}] map fetches: {fetched[:15]}", flush=True)
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
        "clusters": clusters,
        "worker": [w["url"].replace(WEB, "") for w in workers][:1],
        "screenshot": shot.name,
        "passed": bool(ok),
    }


def theme_switch(browser: Browser, errors: list[str]) -> None:
    """Switching the site theme swaps the basemap (setStyle); overlays must return."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    ctx.add_cookies([{"name": "theme", "value": "light", "url": WEB}])
    ctx.add_init_script(DIAGNOSTIC_HOOK)
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"[theme] pageerror: {describe(e)}"))
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
                    try:
                        ledger.append(
                            state(browser, lang=lang, scheme=scheme, phone=phone, errors=errors)
                        )
                    except Exception as exc:  # recorded as a failed state, run continues
                        tag = f"{lang}-{scheme}-{'390' if phone else '1440'}"
                        check(False, f"[{tag}] state crashed: {type(exc).__name__}: {exc}"[:300])
                        ledger.append({"state": tag, "passed": False, "error": type(exc).__name__})
        try:
            theme_switch(browser, errors)
        except Exception as exc:  # recorded, run continues
            check(False, f"[theme] crashed: {type(exc).__name__}: {exc}"[:300])
        browser.close()

    csp = [e for e in errors if "Content Security Policy" in e or "Refused to" in e]
    worker = [e for e in errors if "worker" in e.lower()]
    page_errors = [e for e in errors if "pageerror" in e]
    check(not csp, f"no CSP violations ({csp[:2]})")
    check(not worker, f"no worker errors ({worker[:2]})")
    check(not page_errors, f"no uncaught page errors ({page_errors[:2]})")
    if errors:
        for line in errors[:60]:
            print("  console:", line, flush=True)
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
