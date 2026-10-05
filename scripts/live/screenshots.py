"""Screenshots of the deployed site for design review (desktop + phone, AR/EN,
light/dark, signed-out and signed-in). Writes JPEGs to ./shots.

    WEB_URL=… DEMO_ACCOUNT_PASSWORD=… python scripts/live/screenshots.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB = os.environ["WEB_URL"].rstrip("/")
PASSWORD = os.environ.get("DEMO_ACCOUNT_PASSWORD", "")
OUT = Path("shots")
OUT.mkdir(exist_ok=True)
# "|"-separated (paths may contain commas, e.g. compare ids).
PAGES = os.environ.get(
    "PAGES",
    "/|/properties|/properties/{id}|/map|/compare?ids={id},{id2}"
    "|/search/smart?q=بيت للبيع في البصرة|/pricing|/login|/register|/forgot-password",
).split("|")
AUTH_PAGES = os.environ.get(
    "AUTH_PAGES", "agent:/dashboard,agent:/dashboard/crm,agent:/dashboard/properties,admin:/admin"
).split(",")


def first_ids() -> tuple[str, str]:
    url = f"{WEB}/api/v1/search/properties?page_size=2"
    if not url.startswith("https://"):
        raise SystemExit("WEB_URL must be https")
    for attempt in range(8):  # free instances may still be waking up (502/503)
        try:
            with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 - https checked
                items = json.load(r)["items"]
            return items[0]["id"], items[1]["id"]
        except urllib.error.HTTPError as exc:
            print(f"  waiting for the API ({exc.code}), attempt {attempt + 1}", flush=True)
            time.sleep(20)
    raise SystemExit("API did not answer")


def shoot(page, name: str, path: str) -> None:
    try:
        page.goto(WEB + path, wait_until="load", timeout=120_000)
        page.wait_for_timeout(3500)
        page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=70, full_page=True)
        print(f"  shot {name} ({page.url})", flush=True)
    except Exception as exc:  # keep going: a broken page is itself a finding
        print(f"  FAILED {name}: {type(exc).__name__}: {str(exc)[:200]}", flush=True)


def main() -> None:
    pid, pid2 = first_ids()
    fill = lambda p: p.replace("{id}", pid, 1).replace("{id2}", pid2)  # noqa: E731
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader"])
        variants = [
            ("desk-ar-light", dict(viewport={"width": 1440, "height": 900}), "ar", "light"),
            ("desk-en-dark", dict(viewport={"width": 1440, "height": 900}), "en", "dark"),
            (
                "phone-ar-light",
                dict(
                    viewport={"width": 390, "height": 844},
                    is_mobile=True,
                    has_touch=True,
                    device_scale_factor=2,
                ),
                "ar",
                "light",
            ),
        ]
        for tag, opts, locale, scheme in variants:
            ctx = browser.new_context(**opts, color_scheme=scheme)
            ctx.add_cookies(
                [
                    {"name": "locale", "value": locale, "url": WEB},
                    {"name": "theme", "value": scheme, "url": WEB},
                ]
            )
            page = ctx.new_page()
            for path in PAGES:
                slug = (
                    path.strip("/").split("?")[0].replace("/", "_").replace("{id}", "id") or "home"
                )
                if "{id}" in path and "properties/" in path:
                    slug = "property"
                shoot(page, f"{tag}--{slug}", fill(path))
            ctx.close()
        if PASSWORD:
            for item in AUTH_PAGES:
                who, path = item.split(":", 1)
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                ctx.add_cookies([{"name": "locale", "value": "ar", "url": WEB}])
                r = ctx.request.post(
                    f"{WEB}/api/v1/auth/login",
                    data={"email": f"demo.{who}@example.com", "password": PASSWORD},
                )
                print(f"  login {who}: {r.status}", flush=True)
                page = ctx.new_page()
                shoot(page, f"desk-ar-{who}--{path.strip('/').replace('/', '_')}", path)
                ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
