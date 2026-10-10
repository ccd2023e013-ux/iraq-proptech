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
INSTANT_CACHE: dict[str, tuple[int, dict[str, str], bytes]] = {}

HOOK = r"""
(() => {
  const t0r = performance.now();
  let armed = false, commits = 0;
  const lanes = (n) => '0b' + (n >>> 0).toString(2);
  // Thenable tracking: React's use() and the Flight client record a thenable's
  // state in a `status` field. An accessor on Promise.prototype sees every such
  // write (Flight chunks inherit from Promise.prototype), so after a stuck
  // navigation we can list thenables that never settled and where they came from.
  const ST = Symbol('status');
  const tracked = [];
  Object.defineProperty(Promise.prototype, 'status', {
    configurable: true,
    get() { return this[ST]; },
    set(v) {
      if (this[ST] === undefined && tracked.length < 6000) {
        tracked.push({ p: this, t: (performance.now() - t0r).toFixed(0), first: v, after: armed,
          stack: (new Error().stack || '').split('\n').slice(2, 6).map((x) => x.trim()
            .replace(location.origin, '').replace(/\/_next\/static\/chunks\//g, '')).join(' < ') });
      }
      this[ST] = v;
    },
  });
  const describe = (v) => {
    try {
      if (v === null || v === undefined) return String(v);
      if (typeof v === 'function') return 'fn ' + (v.name || '?');
      if (Array.isArray(v)) return 'array(' + v.length + ')';
      if (typeof v === 'object') return 'obj{' + Object.keys(v).slice(0, 6).join(',') + '}' +
        (v.$$typeof ? ' ' + String(v.$$typeof) : '') + (v.type && v.type.name ? ' type=' + v.type.name : '');
      return typeof v + ' ' + String(v).slice(0, 60);
    } catch (e) { return '?'; }
  };
  // Every <link>/<style> React (Float) inserts after Finish, with load/error events.
  new MutationObserver((records) => {
    if (!armed) return;
    for (const r of records) for (const n of r.addedNodes) {
      if (!(n instanceof Element) || !/^(LINK|STYLE)$/.test(n.tagName)) continue;
      const d = n.tagName + ' rel=' + n.getAttribute('rel') + ' prec=' + n.getAttribute('data-precedence') +
        ' href=' + String(n.getAttribute('href') || '').slice(-60) + ' media=' + n.getAttribute('media');
      qlog('dom+', d);
      n.addEventListener('load', () => qlog('dom-load', d));
      n.addEventListener('error', () => qlog('dom-error', d));
    }
  }).observe(document, { childList: true, subtree: true });
  window.__dbgSheets = () => Array.from(document.querySelectorAll('link[rel=stylesheet],link[rel=preload][as=style],style[data-precedence]'))
    .map((n) => 'sheet ' + n.tagName + ' rel=' + n.getAttribute('rel') + ' prec=' + n.getAttribute('data-precedence') +
      ' href=' + String(n.getAttribute('href') || n.getAttribute('data-href') || '').slice(-60) +
      ' loaded=' + !!(n.sheet) + ' media=' + n.getAttribute('media') +
      ' react=' + Object.keys(n).filter((k) => k.startsWith('_')).join(','));
  window.__dbgPending = () => {
    const r = window.__dbgRoot;
    const out = ['root pending=' + (r ? lanes(r.pendingLanes) : '?') + ' suspended=' + (r ? lanes(r.suspendedLanes) : '?') +
      ' pinged=' + (r ? lanes(r.pingedLanes) : '?') + ' callbackNode=' + (r ? !!r.callbackNode : '?') +
      ' tracked=' + tracked.length];
    const counts = {};
    for (const x of tracked) counts[x.p[ST]] = (counts[x.p[ST]] || 0) + 1;
    out.push('final statuses ' + JSON.stringify(counts));
    for (const x of tracked) {
      const st = x.p[ST];
      if (st === 'fulfilled' || st === 'rejected') continue;
      out.push('UNSETTLED ' + (x.after ? 'after' : 'BEFORE') + '-finish t=' + x.t + ' status=' + st + ' (first ' + x.first + ') ctor=' +
        (x.p.constructor && x.p.constructor.name) + ' value=' + describe(x.p.value) +
        ' reason=' + describe(x.p.reason) + ' | ' + x.stack);
      if (out.length > 60) break;
    }
    return out;
  };
  const qlog = (...a) => console.warn('[dbg] ' + (performance.now() - t0r).toFixed(0).padStart(5) + ' ' + a.join(' '));
  const pageSeg = (tree) => {
    // Walk children slots down to the leaf page segment.
    try {
      let t = tree, path = [];
      for (let i = 0; i < 12 && t; i++) {
        path.push(typeof t[0] === 'string' ? t[0] : JSON.stringify(t[0]));
        t = t[1] && t[1].children;
      }
      return path.join('/').slice(0, 160);
    } catch (e) { return '?'; }
  };
  const node = (n) => n ? (n.payload.type + (n.discarded ? '(discarded)' : '')) : 'null';
  // Next 15's app-router action queue is a prop of the AppRouter component; wrap
  // its dispatch/action to see every router action, the queue state, and results.
  const findQueue = (fiber) => {
    const stack = [fiber];
    let seen = 0;
    while (stack.length && seen < 5000) {
      const f = stack.pop(); seen++;
      const q = f && f.memoizedProps && f.memoizedProps.actionQueue;
      if (q && typeof q.dispatch === 'function' && typeof q.action === 'function') {
        window.__dbgQueue = q;
        let id = 0;
        const dispatch = q.dispatch;
        q.dispatch = (payload, setState) => {
          const url = payload.url ? String(payload.url).replace(location.origin, '').slice(0, 70) : '';
          qlog('Q.dispatch', payload.type, url, '| pending=' + node(q.pending), 'last=' + node(q.last),
               'lastIsPending=' + (q.last === q.pending));
          return dispatch(payload, setState);
        };
        const action = q.action;
        q.action = (state, payload) => {
          const n = ++id;
          qlog('Q.run#' + n, payload.type, 'from tree=' + pageSeg(state.tree));
          const r = action(state, payload);
          Promise.resolve(r).then(
            (s) => qlog('Q.done#' + n, payload.type, s === state ? 'UNCHANGED-STATE' : 'new-state',
                        'tree=' + pageSeg(s && s.tree), 'url=' + (s && s.canonicalUrl || '').slice(0, 60),
                        '| pending=' + node(q.pending)),
            (e) => qlog('Q.fail#' + n, payload.type, String(e).slice(0, 120)));
          return r;
        };
        qlog('action queue wrapped');
        return;
      }
      if (f.sibling) stack.push(f.sibling);
      if (f.child) stack.push(f.child);
    }
  };
  window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {
    supportsFiber: true, isDisabled: false, renderers: new Map(),
    inject(renderer) { const id = this.renderers.size + 1; this.renderers.set(id, renderer); return id; },
    checkDCE() {}, onScheduleFiberRoot() {}, onCommitFiberUnmount() {}, onPostCommitFiberRoot() {},
    onCommitFiberRoot(id, root) {
      window.__dbgRoot = root;
      if (!window.__dbgQueue) findQueue(root.current);
      commits += 1;
      if (armed && commits < 400) console.warn('[dbg] ' + (performance.now() - t0r).toFixed(0).padStart(5) +
        ' react-commit #' + commits + ' pending=' + lanes(root.pendingLanes) +
        ' suspended=' + lanes(root.suspendedLanes) + ' pinged=' + lanes(root.pingedLanes));
    },
  };
  addEventListener('click', (e) => {
    const el = e.target && e.target.closest && e.target.closest('[data-testid=finish-area]');
    if (el) { armed = true; commits = 0; }
  }, true);
  setTimeout(() => {}, 0);
})();
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
    let tree = '';
    try {
      const h = new Headers((init && init.headers) || (input instanceof Request ? input.headers : undefined));
      tree = decodeURIComponent(h.get('Next-Router-State-Tree') || '');
    } catch (e) {}
    const kind = tree.includes('refetch') ? 'LAZY(refetch-marker)' : 'NAV';
    log('fetch>', kind, u, 'signal=' + !!sig, '|', stack());
    log('tree>', tree.replace(/"/g, '').slice(0, 330));
    if (sig) sig.addEventListener('abort', () => log('signal-abort', u, String(sig.reason).slice(0, 90)));
    return realFetch(input, init).then(
      (r) => {
        log('fetch<', r.status, u);
        try {
          r.clone().text().then(
            (b) => log('body', b.length + 'B', JSON.stringify(b.slice(0, 260))),
            (e) => log('body!', String(e).slice(0, 90)));
        } catch (e) {}
        return r;
      },
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


def attempt(
    browser, n: int, forced: bool, delay_ms: int | None = None, throttle: float = 1
) -> tuple[bool, list[str], bool]:
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
    ctx.add_init_script(HOOK)
    page = ctx.new_page()
    log: list[str] = []
    start = time.monotonic()
    stamp = lambda: f"{(time.monotonic() - start) * 1000:6.0f}"  # noqa: E731
    page.on(
        "console",
        lambda m: log.append(m.text[:600])
        if m.text.startswith("[dbg]")
        else (log.append(f"[con] {stamp()} {m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None),
    )
    page.on("pageerror", lambda e: log.append(f"[pageerror] {stamp()} {str(e)[:300]}"))
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
    if os.environ.get("INSTANT") == "1":
        # Serve the polygon RSC from a cache filled by the first attempt: the
        # response is available immediately (faster than any real round trip).
        def instant(route):
            key = route.request.url.split("&_rsc=")[0]
            hit = INSTANT_CACHE.get(key)
            if hit is None:
                response = route.fetch()
                hit = (response.status, dict(response.headers), response.body())
                INSTANT_CACHE[key] = hit
                log.append(f"[pw] {stamp()} polygon RSC fetched for cache ({len(hit[2])}B)")
            else:
                log.append(f"[pw] {stamp()} polygon RSC served instantly from cache")
            status, headers, body = hit
            headers = {k: v for k, v in headers.items() if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")}
            route.fulfill(status=status, headers=headers, body=body)

        page.route(lambda url: "polygon=" in url and "_rsc=" in url, instant)
    if delay_ms is not None:
        # Hold the polygon RSC response for delay_ms after the server answered.
        def hold(route):
            response = route.fetch()
            time.sleep(delay_ms / 1000)
            route.fulfill(response=response)
            log.append(f"[pw] {stamp()} fulfilled polygon RSC after +{delay_ms}ms hold")

        page.route(lambda url: "polygon=" in url and "_rsc=" in url, hold)
    page.goto(WEB + BASRA, wait_until="load", timeout=120_000)
    canvas = page.locator("[data-testid=map-canvas]")
    for _ in range(60):
        if int(canvas.get_attribute("data-bubbles") or 0) > 0:
            break
        page.wait_for_timeout(1_000)
    box = canvas.bounding_box()
    if forced:
        # Pan the map (moveend schedules the 450 ms viewport update), then start
        # drawing inside that window — the race seen in the failing natural run.
        page.wait_for_timeout(1_500)
        x0, y0 = box["x"] + box["width"] * 0.7, box["y"] + box["height"] * 0.3
        page.mouse.move(x0, y0)
        page.mouse.down()
        page.mouse.move(x0 - 40, y0 + 25, steps=6)
        page.mouse.up()
        page.wait_for_timeout(120)
    log.append(f"[pw] {stamp()} ---- map ready, start drawing (forced={forced})")
    page.locator("[data-testid=draw-area]").click()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for dx, dy in ((-120, -90), (130, -80), (0, 120)):
        page.mouse.click(cx + dx, cy + dy)
        page.wait_for_timeout(700)
    if throttle > 1:
        # Slow the renderer's CPU from here on: React's render of the navigation
        # takes longer, so the RSC response lands while it is still rendering.
        cdp = ctx.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
        log.append(f"[pw] {stamp()} cpu throttle x{throttle}")
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
    try:
        for line in page.evaluate("() => window.__dbgPending ? window.__dbgPending() : ['no tracker']"):
            log.append(f"[post] {line[:700]}")
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        log.append(f"[post] tracker failed: {exc}")
    if not ok and os.environ.get("LATE") == "1":
        # Does the stuck navigation commit LATE? React holds a commit that waits on
        # suspensey resources (stylesheets) for up to 60 s before giving up.
        late_at = None
        for k in range(160):
            if "polygon=" in page.url:
                late_at = k * 0.5
                break
            page.wait_for_timeout(500)
        log.append(f"[post] late commit after extra wait: {late_at}s" if late_at is not None
                   else "[post] still not committed after +80s")
        try:
            for line in page.evaluate("() => window.__dbgSheets ? window.__dbgSheets() : []"):
                log.append(f"[post] {line[:500]}")
        except Exception as exc:  # noqa: BLE001
            log.append(f"[post] sheets failed: {exc}")
    skeleton = page.locator("[role=status][aria-busy]").count()
    map_alive = page.locator("[data-testid=map-canvas]").count()
    log.append(
        f"[pw] {stamp()} ---- end url={page.url.replace(WEB, '')[:80]} ok={ok}"
        f" loading_skeleton={skeleton} map_element={map_alive}"
    )
    # Did a bbox navigation start after the draw-area click?
    drew = next((i for i, line in enumerate(log) if "click draw-area" in line), None)
    bbox_during = drew is not None and any(
        "router.replace /map?bbox" in line for line in log[drew:]
    )
    ctx.close()
    return ok, log, bbox_during


def sweep(delays: list[int], reps: int) -> int:
    rows: list[str] = []
    first_fail: tuple[str, list[str]] | None = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        for d in delays:
            marks = []
            for r in range(reps):
                ok, log, _ = attempt(browser, r + 1, False, d)
                marks.append("P" if ok else "F")
                print(f"delay {d}ms rep {r + 1}: {'PASS' if ok else 'FAIL'}", flush=True)
                if not ok and first_fail is None:
                    first_fail = (f"{d}ms rep {r + 1}", log)
            rows.append(f"{d}ms: {marks.count('P')}/{reps} {''.join(marks)}")
        browser.close()
    print("::notice title=draw debug delay sweep::" + " | ".join(rows), flush=True)
    if first_fail:
        i = max((k for k, line in enumerate(first_fail[1]) if "map ready" in line), default=0)
        text = " ⏎ ".join(line.split(" | at ")[0] for line in first_fail[1][i:] if "tree>" not in line)
        print(f"::notice title=draw debug sweep FAIL {first_fail[0]}::{text[:9000]}", flush=True)
    return 0


def split_sweep(configs: list[str], reps: int) -> int:
    """Run through rsc_split_proxy.py, streaming the polygon RSC in two timed parts."""
    import subprocess
    import urllib.request

    global WEB
    upstream = WEB
    proxy = subprocess.Popen(
        ["python", "scripts/ci/rsc_split_proxy.py", "--upstream", upstream, "--port", "3100"]
    )
    WEB = "http://localhost:3100"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(WEB + "/__split", timeout=2).read()
                break
            except OSError:
                time.sleep(0.2)
        rows: list[str] = []
        first_fail: tuple[str, list[str]] | None = None
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
            )
            for cfg in configs:
                at, _, gap = cfg.partition("@")
                urllib.request.urlopen(f"{WEB}/__split?at={at}&gap={gap or 0}&reset=1").read()
                marks = []
                for r in range(reps):
                    ok, log, _ = attempt(browser, r + 1, False)
                    marks.append("P" if ok else "F")
                    print(f"split {cfg} rep {r + 1}: {'PASS' if ok else 'FAIL'}", flush=True)
                    if not ok and first_fail is None:
                        first_fail = (cfg, log)
                hits = urllib.request.urlopen(f"{WEB}/__split").read().decode()
                rows.append(f"{cfg}: {marks.count('P')}/{reps} {''.join(marks)} {hits}")
            browser.close()
        print("::notice title=draw debug split sweep::" + " | ".join(rows), flush=True)
        if first_fail:
            i = max((k for k, line in enumerate(first_fail[1]) if "map ready" in line), default=0)
            text = " ⏎ ".join(
                line if line.startswith("[post]") else line.split(" | at ")[0]
                for line in first_fail[1][i:]
                if "tree>" not in line and " Q." not in line
            )
            print(f"::notice title=draw debug split FAIL {first_fail[0]}::{text[:9000]}", flush=True)
    finally:
        proxy.terminate()
        WEB = upstream
    return 0


def throttle_sweep(rates: list[float], reps: int) -> int:
    rows: list[str] = []
    first_fail: tuple[str, list[str]] | None = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        for rate in rates:
            marks = []
            for r in range(reps):
                ok, log, _ = attempt(browser, r + 1, False, None, rate)
                marks.append("P" if ok else "F")
                print(f"throttle x{rate} rep {r + 1}: {'PASS' if ok else 'FAIL'}", flush=True)
                if not ok and first_fail is None:
                    first_fail = (f"x{rate}", log)
            rows.append(f"x{rate}: {marks.count('P')}/{reps} {''.join(marks)}")
        browser.close()
    print("::notice title=draw debug cpu-throttle sweep::" + " | ".join(rows), flush=True)
    if first_fail:
        i = max((k for k, line in enumerate(first_fail[1]) if "map ready" in line), default=0)
        text = " ⏎ ".join(
            line if line.startswith("[post]") else line.split(" | at ")[0]
            for line in first_fail[1][i:]
            if "tree>" not in line
        )
        print(f"::notice title=draw debug throttle FAIL {first_fail[0]}::{text[:9000]}", flush=True)
    return 0


def main() -> int:
    if os.environ.get("THROTTLES"):
        rates = [float(x) for x in os.environ["THROTTLES"].split(",")]
        return throttle_sweep(rates, int(os.environ.get("REPS", "8")))
    if os.environ.get("SPLITS"):
        return split_sweep(os.environ["SPLITS"].split(","), int(os.environ.get("REPS", "4")))
    if os.environ.get("DELAYS"):
        delays = [int(x) for x in os.environ["DELAYS"].split(",")]
        return sweep(delays, int(os.environ.get("REPS", "6")))
    results: list[bool] = []
    fails: list[tuple[int, list[str]]] = []
    first_pass: tuple[int, list[str]] | None = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        table: list[str] = []
        for n in range(1, ATTEMPTS + 1):
            forced = n > ATTEMPTS // 2
            ok, log, bbox_during = attempt(browser, n, forced)
            results.append(ok)
            table.append(
                f"{n}{'f' if forced else 'n'}:{'P' if ok else 'F'}{'+B' if bbox_during else ''}"
            )
            print(f"attempt {n}: {'PASS' if ok else 'FAIL'} forced={forced} bbox_during={bbox_during}", flush=True)
            if not ok:
                fails.append((n, log))
            elif first_pass is None:
                first_pass = (n, log)
        print(
            "::notice title=draw debug correlation::n=natural f=forced; P/F=pass/fail; "
            "+B=a bbox navigation started after the draw click — " + " ".join(table),
            flush=True,
        )
        browser.close()
    summary = " ".join(f"{i}:{'P' if r else 'F'}" for i, r in enumerate(results, 1))
    print(
        f"::notice title=draw debug summary::{results.count(True)}/{ATTEMPTS} passed — {summary}",
        flush=True,
    )

    def tail(log: list[str]) -> str:
        i = max((k for k, line in enumerate(log) if "map ready" in line), default=0)
        late = [line for line in log[i:] if "tree>" not in line and " body " not in line]
        text = " ⏎ ".join(
            line if line.startswith("[post]") else line.split(" | at ")[0] for line in late
        )
        return text[:12000]

    if first_pass:
        print(f"::notice title=draw debug PASS #{first_pass[0]}::{tail(first_pass[1])}", flush=True)
    for n, log in fails[:6]:
        print(f"::notice title=draw debug FAIL #{n}::{tail(log)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
