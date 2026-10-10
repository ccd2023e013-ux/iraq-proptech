"""DIAGNOSTIC ONLY (issue #4) — not a gate; lives on a throwaway debug branch.

Repeats the /map draw-area flow and records, with timestamps, everything that
can make the App Router drop the polygon navigation: RSC fetches (any input
type), AbortController/AbortSignal aborts with call stacks, stream/reader
cancels, history changes, the Next router's own push/replace/refresh calls,
form submits, page unloads, plus Playwright's view of each RSC request.

    WEB_URL=http://localhost:3000 python scripts/ci/draw_debug.py
"""

from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

WEB = os.environ.get("WEB_URL", "http://localhost:3000").rstrip("/")
ATTEMPTS = int(os.environ.get("ATTEMPTS", "30"))
BASRA = "/map?bbox=47.70,30.40,47.92,30.62"

HOOK = r"""
(() => {
  const t0 = performance.now();
  const T = () => (performance.now() - t0).toFixed(0).padStart(5);
  const log = (...a) => console.warn('[dbg] ' + T() + ' ' + a.join(' '));
  const short = (u) => {
    try { return String(u && u.url ? u.url : u).replace(location.origin, '').slice(0, 100); }
    catch (e) { return '?'; }
  };
  const stack = () => (new Error().stack || '').split('\n').slice(2, 7)
    .map((s) => s.trim().replace(location.origin, '')).join(' < ').slice(0, 420);
  const realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const u = short(input);
    let rsc = u.includes('_rsc=');
    try {
      const h = init && init.headers;
      if (h instanceof Headers) rsc = rsc || h.has('RSC');
      else if (h) rsc = rsc || JSON.stringify(h).includes('RSC');
      if (input instanceof Request) rsc = rsc || input.headers.has('RSC');
    } catch (e) {}
    if (!rsc) return realFetch(input, init);
    const sig = (init && init.signal) || (input instanceof Request ? input.signal : undefined);
    log('fetch>', u, 'signal=' + !!sig, '|', stack());
    if (sig) sig.addEventListener('abort', () => log('signal-abort', u, String(sig.reason).slice(0, 90)));
    return realFetch(input, init).then(
      (r) => { log('fetch<', r.status, u); return r; },
      (e) => { log('fetch!', u, String(e).slice(0, 90)); throw e; });
  };
  const abort = AbortController.prototype.abort;
  AbortController.prototype.abort = function (reason) {
    log('abort()', String(reason).slice(0, 70), '|', stack());
    return abort.call(this, reason);
  };
  for (const name of ['pushState', 'replaceState']) {
    const original = history[name].bind(history);
    history[name] = (s, t, url) => { log(name, short(url)); return original(s, t, url); };
  }
  const readerCancel = ReadableStreamDefaultReader.prototype.cancel;
  ReadableStreamDefaultReader.prototype.cancel = function (r) {
    log('reader.cancel', String(r).slice(0, 70), '|', stack());
    return readerCancel.call(this, r);
  };
  const streamCancel = ReadableStream.prototype.cancel;
  ReadableStream.prototype.cancel = function (r) {
    log('stream.cancel', String(r).slice(0, 70), '|', stack());
    return streamCancel.call(this, r);
  };
  addEventListener('submit', (e) => log('submit', e.target && e.target.action), true);
  addEventListener('pagehide', () => log('pagehide'));
  addEventListener('beforeunload', () => log('beforeunload'));
  addEventListener('popstate', () => log('popstate', short(location.href)));
  addEventListener('click', (e) => {
    const el = e.target && e.target.closest && e.target.closest('[data-testid]');
    if (el && /finish-area|draw-area/.test(el.dataset.testid)) log('click', el.dataset.testid);
  }, true);
  const wrapRouter = () => {
    const r = window.next && window.next.router;
    if (!r) return false;
    if (r.__dbg) return true;
    for (const k of ['push', 'replace', 'refresh']) {
      if (typeof r[k] !== 'function') continue;
      const o = r[k].bind(r);
      r[k] = (...a) => { log('router.' + k, short(a[0]), '|', stack()); return o(...a); };
    }
    r.__dbg = true;
    log('router wrapped');
    return true;
  };
  const iv = setInterval(() => { if (wrapRouter()) clearInterval(iv); }, 50);
})();
"""


def attempt(browser, n: int) -> tuple[bool, list[str]]:
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
    ctx.add_init_script(HOOK)
    page = ctx.new_page()
    log: list[str] = []
    start = time.monotonic()
    stamp = lambda: f"{(time.monotonic() - start) * 1000:6.0f}"  # noqa: E731
    page.on("console", lambda m: log.append(m.text[:600]) if m.text.startswith("[dbg]") else None)
    page.on(
        "framenavigated",
        lambda f: log.append(f"[pw] {stamp()} framenavigated {f.url.replace(WEB, '')[:100]}")
        if f == page.main_frame
        else None,
    )
    for event in ("request", "requestfinished", "requestfailed"):
        page.on(
            event,
            lambda r, event=event: log.append(
                f"[pw] {stamp()} {event} {r.url.replace(WEB, '')[:90]}"
                + (f" {r.failure}" if event == "requestfailed" else "")
            )
            if "_rsc=" in r.url
            else None,
        )
    page.goto(WEB + BASRA, wait_until="load", timeout=120_000)
    canvas = page.locator("[data-testid=map-canvas]")
    for _ in range(60):
        if int(canvas.get_attribute("data-bubbles") or 0) > 0:
            break
        page.wait_for_timeout(1_000)
    log.append(f"[pw] {stamp()} ---- map ready, start drawing")
    page.locator("[data-testid=draw-area]").click()
    box = canvas.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for dx, dy in ((-120, -90), (130, -80), (0, 120)):
        page.mouse.click(cx + dx, cy + dy)
        page.wait_for_timeout(700)
    log.append(f"[pw] {stamp()} ---- click Finish")
    page.locator("[data-testid=finish-area]").click()
    ok = False
    for _ in range(30):
        if "polygon=" in page.url:
            ok = True
            break
        page.wait_for_timeout(500)
    page.wait_for_timeout(2_000)
    ok = ok and "polygon=" in page.url
    log.append(f"[pw] {stamp()} ---- end url={page.url.replace(WEB, '')[:80]} ok={ok}")
    ctx.close()
    return ok, log


def main() -> int:
    results: list[bool] = []
    fails: list[tuple[int, list[str]]] = []
    first_pass: tuple[int, list[str]] | None = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        for n in range(1, ATTEMPTS + 1):
            ok, log = attempt(browser, n)
            results.append(ok)
            print(f"attempt {n}: {'PASS' if ok else 'FAIL'}", flush=True)
            if not ok:
                fails.append((n, log))
            elif first_pass is None:
                first_pass = (n, log)
        browser.close()
    summary = " ".join(f"{i}:{'P' if r else 'F'}" for i, r in enumerate(results, 1))
    print(
        f"::notice title=draw debug summary::{results.count(True)}/{ATTEMPTS} passed — {summary}",
        flush=True,
    )

    def tail(log: list[str]) -> str:
        i = max((k for k, line in enumerate(log) if "map ready" in line), default=0)
        return " ⏎ ".join(log[i:])[:6000]

    if first_pass:
        print(f"::notice title=draw debug PASS #{first_pass[0]}::{tail(first_pass[1])}", flush=True)
    for n, log in fails[:6]:
        print(f"::notice title=draw debug FAIL #{n}::{tail(log)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
