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
    third_party_scripts: list[str] = []
    page.on(
        "request",
        lambda r: (
            third_party_scripts.append(r.url[:120])
            if "unpkg.com" in r.url or (r.resource_type == "script" and not r.url.startswith(WEB))
            else None
        ),
    )
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
    ok &= check(
        not third_party_scripts,
        f"[{tag}] no third-party script (no RTL plugin from unpkg) {third_party_scripts[:2]}",
    )
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


DRAW_ATTEMPTS = 20
DRAW_AREA_ISSUE = "https://github.com/ccd2023e013-ux/iraq-proptech/issues/4"


def draw_area(browser: Browser) -> None:
    """Draw-area search, repeated (issue #4): finishing a drawn area must always
    land on a polygon URL and keep it. Every attempt must pass.

    Even attempts first let the page settle, then pan the map and click "Draw
    area" inside the 450 ms viewport debounce: the pending viewport update must
    be dropped, so the URL must not change at all while drawing (deterministic:
    before the fix every such attempt navigated to the panned bbox mid-draw).
    Odd attempts draw as soon as the map shows bubbles, so a viewport
    navigation already in flight may still commit while drawing; they only
    check the outcome. Logs every URL the page commits so a failure shows what
    overwrote what."""
    passed = 0
    sample: dict[bool, str] = {}  # first passing / first failing trace (issue #4)
    for attempt in range(1, DRAW_ATTEMPTS + 1):
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
        ctx.add_init_script(DIAGNOSTIC_HOOK)
        page = ctx.new_page()
        urls: list[str] = []
        console: list[str] = []
        trace: list[str] = []  # router activity after Finish (issue #4)
        tracing = [False]
        page.on(
            "request",
            lambda r, trace=trace, tracing=tracing: (
                trace.append(f"rsc> {r.url.replace(WEB, '')[:120]}")
                if tracing[0] and "_rsc=" in r.url
                else None
            ),
        )
        page.on(
            "requestfinished",
            lambda r, trace=trace, tracing=tracing: (
                trace.append(f"rsc< {r.url.replace(WEB, '')[:60]}… done")
                if tracing[0] and "_rsc=" in r.url
                else None
            ),
        )
        page.on(
            "requestfailed",
            lambda r, trace=trace, tracing=tracing: (
                trace.append(f"rsc✗ {r.url.replace(WEB, '')[:60]}… {r.failure}")
                if tracing[0] and "_rsc=" in r.url
                else None
            ),
        )
        page.on(
            "console",
            lambda m, console=console: (
                console.append(f"{m.type}: {m.text[:200]}")
                if m.type in ("error", "warning")
                else None
            ),
        )
        page.on(
            "framenavigated",
            lambda f, urls=urls, page=page: (
                urls.append(f.url.replace(WEB, "")[:140]) if f == page.main_frame else None
            ),
        )
        page.goto(WEB + BASRA, wait_until="load", timeout=120_000)
        if poll_bubbles(page) == 0:
            check(False, f"[draw {attempt}] map drew no bubbles")
            ctx.close()
            continue
        box = page.locator("[data-testid=map-canvas]").bounding_box()
        if box is None:
            check(False, f"[draw {attempt}] map has no bounding box")
            ctx.close()
            continue
        pan_first = attempt % 2 == 0
        if pan_first:
            page.wait_for_timeout(1_500)  # let the load-time viewport update settle
            x0, y0 = box["x"] + box["width"] * 0.7, box["y"] + box["height"] * 0.3
            page.mouse.move(x0, y0)
            page.mouse.down()
            page.mouse.move(x0 - 40, y0 + 25, steps=6)
            page.mouse.up()
            page.wait_for_timeout(120)  # well inside the 450 ms debounce
        urls_at_draw = len(urls)
        page.locator("[data-testid=draw-area]").click()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for dx, dy in ((-120, -90), (130, -80), (0, 120)):
            page.mouse.click(cx + dx, cy + dy)
            page.wait_for_timeout(700)
        finish = page.locator("[data-testid=finish-area]")
        page.wait_for_timeout(600)  # > debounce: a stale viewport update would land now
        moved_while_drawing = urls[urls_at_draw:] if pan_first else []
        enabled_before = finish.is_enabled()
        tracing[0] = True
        finish.click()
        landed = False
        for _ in range(30):
            if "polygon=" in page.url:
                landed = True
                break
            page.wait_for_timeout(500)
        page.wait_for_timeout(2_000)  # a late viewport update would replace it here
        kept = "polygon=" in page.url
        ok = landed and kept and not moved_while_drawing
        passed += int(ok)
        detail = f" pan_first={pan_first} moved_while_drawing={moved_while_drawing}"
        if not ok:
            # Did the click end draw mode? Did the search counter change?
            detail += (
                f" enabled_before={enabled_before}"
                f" still_drawing={page.locator('[data-testid=finish-area]').count() > 0}"
                f" draw_button={page.locator('[data-testid=draw-area]').count() > 0}"
                f" total={page.locator('[data-testid=map-total]').inner_text()[:60]!r}"
                f" console={console[-4:]}"
            )
        detail += f" trace={trace[:14]}"
        sample.setdefault(ok, f"attempt {attempt}: {trace[:24]}")
        if not ok:  # each failure as a notice: the job log is not always retrievable
            print(
                f"::notice title=draw attempt {attempt} FAILED::landed={landed} kept={kept} "
                f"pan_first={pan_first} moved_while_drawing={moved_while_drawing} "
                f"urls={urls[-6:]} trace={trace[:14]}"[:3000],
                flush=True,
            )
        print(
            f"  {'✓' if ok else '✗'} [draw {attempt}] landed={landed} kept={kept} "
            f"urls={urls[-6:]}{detail}",
            flush=True,
        )
        ctx.close()
    for ok, text in sample.items():  # notices are kept even when the step passes
        print(f"::notice title=draw trace ({'pass' if ok else 'FAIL'})::{text[:3000]}", flush=True)
    # Gating: every attempt must land on and keep the polygon (DRAW_AREA_ISSUE).
    check(
        passed == DRAW_ATTEMPTS,
        f"draw-area search works ({passed}/{DRAW_ATTEMPTS} attempts) — see {DRAW_AREA_ISSUE}",
    )


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
        try:
            draw_area(browser)
        except Exception as exc:  # recorded, run continues
            check(False, f"[draw] crashed: {type(exc).__name__}: {exc}"[:300])
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
