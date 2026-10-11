"""Source representative DEMO listing photos from Wikimedia Commons.

Two modes (run by .github/workflows/demo-photos.yml on a GitHub runner, since
the photos must be fetched from the internet):

  survey  Search Commons for candidate photos of Iraqi residential and
          commercial buildings, keep only files whose licence metadata (from
          the Commons API) is free and attribution-compatible, and write
          numbered contact sheets plus candidates.json for human review.

  fetch   Download the reviewed files (KIND|File:Title lines), re-check each
          licence, resize to 1600 px, strip all metadata (EXIF/GPS) and write
          backend/app/demo_photos/<n>.jpg with manifest.json holding the full
          attribution (title, author, source page, licence and licence URL).

Accepted licences: public domain, CC0, CC BY and CC BY-SA (2.0-4.0). Files
with "restrictions" (personality rights, trademarks...) or flagged NonFree
are rejected. Nothing here decides that a photo shows a specific listing: the
photos are representative only and the app labels them that way.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

API = "https://commons.wikimedia.org/w/api.php"
UA = "MAKAN-demo-photos/1.0 (https://github.com/ccd2023e013-ux/iraq-proptech; demo data)"
LICENCE_OK = re.compile(
    r"^(public domain|pd(-.*)?|cc0( 1\.0)?|cc[- ]by(-sa)?[- ](2\.0|2\.5|3\.0|4\.0)( .*)?)$", re.I
)
CATEGORIES = [
    "Neighbourhoods of Baghdad",
    "Neighborhoods of Baghdad",
    "Neighbourhoods of Basra",
    "Neighbourhoods of Erbil",
    "Districts of Baghdad",
    "Residential areas in Iraq",
    "Housing estates in Iraq",
    "Gated communities in Iraq",
    "English Village (Erbil)",
    "Italian Village (Erbil)",
    "Dream City (Erbil)",
    "Empire World (Erbil)",
    "Bismayah New City",
    "Apartment buildings in Erbil",
    "Apartment buildings in Baghdad",
    "Houses in Sulaymaniyah",
    "Houses in Duhok",
    "Architecture of Basra",
    "Architecture of Erbil",
    "Al-Mansour",
    "Karrada",
    "Zayouna",
    "Streets in Sulaymaniyah",
    "Streets in Najaf",
    "Streets in Karbala",
    "Markets in Baghdad",
    "Commercial buildings in Iraq",
    "Construction in Iraq",
    "Agricultural land in Iraq",
    "Date palm plantations in Iraq",
]
SEARCHES = [
    "Erbil residential complex",
    "Erbil villas",
    "Duhok houses",
    "Sulaymaniyah residential",
    "Baghdad residential area",
    "Mansour Baghdad street",
    "Zayouna Baghdad",
    "Basra residential street",
    "Basra apartments",
    "Basra Jazair",
    "Najaf street houses",
    "Karbala residential",
    "Mosul new houses",
    "Kirkuk residential",
    "Nasiriyah street",
    "Amarah houses",
    "Hillah street",
    "Iraq apartment complex construction",
    "Erbil skyline apartments",
    "Iraq farmland palm grove",
]
# Military/official photography and archive scans are not suitable as homes.
EXCLUDE = re.compile(
    r"DVIDS|Operation|U\.S\. Army|Department of (Defense|State)|Sgt\.|Spc\.|Embassy|DPLA|"
    r"soldier|Marines|Airmen|Navy|ruin|destroy|damage|Jewish|Mosque|Shrine|Church|Museum",
    re.I,
)


def api(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https host
                return json.load(resp)
        except Exception:  # retried, then raised
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 3)
    return {}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - Commons upload host
        return resp.read()


def clean(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def info(titles: list[str], width: int) -> list[dict]:
    """Licence and URL metadata for up to 50 file titles."""
    out = []
    for i in range(0, len(titles), 40):
        data = api(
            {
                "action": "query",
                "titles": "|".join(titles[i : i + 40]),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": str(width),
            }
        )
        for page in data.get("query", {}).get("pages", []):
            ii = (page.get("imageinfo") or [None])[0]
            if not ii:
                continue
            meta = ii.get("extmetadata", {})
            m = lambda k: clean(meta.get(k, {}).get("value"))  # noqa: E731
            out.append(
                {
                    "title": page["title"],
                    "page": ii.get("descriptionurl"),
                    "url": ii.get("thumburl") or ii.get("url"),
                    "width": ii.get("width"),
                    "height": ii.get("height"),
                    "mime": ii.get("mime"),
                    "licence": m("LicenseShortName"),
                    "licence_url": m("LicenseUrl"),
                    "author": m("Artist") or m("Credit"),
                    "credit": m("Credit"),
                    "restrictions": m("Restrictions"),
                    "non_free": m("NonFree"),
                    "description": m("ImageDescription")[:200],
                }
            )
    return out


def acceptable(c: dict, min_width: int = 1000) -> str | None:
    """None when usable, otherwise the reason it is rejected."""
    if c["mime"] not in ("image/jpeg", "image/png"):
        return "not a photo"
    if not LICENCE_OK.match(c["licence"] or ""):
        return f"licence {c['licence']!r}"
    if c["non_free"] and c["non_free"].lower() not in ("false", "0"):
        return "non-free"
    if c["restrictions"]:
        return f"restrictions {c['restrictions']!r}"
    if not c["author"]:
        return "no author"
    if (c["width"] or 0) < min_width or (c["height"] or 0) < min_width * 0.6:
        return "too small"
    ratio = (c["width"] or 1) / (c["height"] or 1)
    if not 1.1 <= ratio <= 2.0:
        return "not landscape"
    return None


def survey(out: Path) -> None:
    titles: dict[str, str] = {}
    cats = list(CATEGORIES)
    for cat in CATEGORIES:
        data = api(
            {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": f"Category:{cat}",
                "cmtype": "subcat",
                "cmlimit": "40",
            }
        )
        for m in data.get("query", {}).get("categorymembers", []):
            cats.append(m["title"].removeprefix("Category:"))
    print(f"{len(cats)} categories", flush=True)
    for cat in cats:
        cont: dict = {}
        for _ in range(2):
            data = api(
                {
                    "action": "query",
                    "list": "categorymembers",
                    "cmtitle": f"Category:{cat}",
                    "cmtype": "file",
                    "cmlimit": "200",
                    **cont,
                }
            )
            for m in data.get("query", {}).get("categorymembers", []):
                titles.setdefault(m["title"], cat)
            cont = data.get("continue", {})
            if not cont:
                break
    for q in SEARCHES:
        data = api(
            {"action": "query", "list": "search", "srsearch": f"{q} filetype:bitmap", "srnamespace": "6", "srlimit": "60"}
        )
        for m in data.get("query", {}).get("search", []):
            titles.setdefault(m["title"], f"search: {q}")
    print(f"{len(titles)} titles found", flush=True)
    metas = info(list(titles), 400)
    keep, rejected = [], {}
    for c in metas:
        reason = acceptable(c)
        if not reason and EXCLUDE.search(f"{c['title']} {c['author']} {c['description']}"):
            reason = "excluded subject"
        if reason:
            rejected[reason.split(" ")[0]] = rejected.get(reason.split(" ")[0], 0) + 1
            continue
        c["source"] = titles[c["title"]]
        keep.append(c)
    print(f"{len(keep)} acceptable; rejected: {rejected}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=22)
    per_sheet, cols, tw, th = 24, 6, 400, 300
    for s in range(0, len(keep), per_sheet):
        sheet = Image.new("RGB", (cols * tw, (per_sheet // cols) * (th + 30)), (30, 30, 30))
        draw = ImageDraw.Draw(sheet)
        for j, c in enumerate(keep[s : s + per_sheet]):
            n = s + j
            c["n"] = n
            x, y = (j % cols) * tw, (j // cols) * (th + 30)
            try:
                im = Image.open(io.BytesIO(download(c["url"]))).convert("RGB")
                im = ImageOps.fit(im, (tw - 6, th - 6))
                sheet.paste(im, (x + 3, y + 3))
            except Exception as exc:  # recorded on the sheet
                draw.text((x + 10, y + 100), f"failed {type(exc).__name__}", fill=(255, 80, 80), font=font)
            draw.text((x + 6, y + th + 2), f"#{n} {c['licence']}", fill=(255, 220, 120), font=font)
            time.sleep(0.2)
        sheet.save(out / f"sheet-{s // per_sheet:02d}.jpg", quality=80)
    (out / "candidates.json").write_text(json.dumps(keep, indent=1, ensure_ascii=False))


def fetch(spec: str, out: Path) -> None:
    wanted = []
    for line in spec.replace(";", "\n").splitlines():
        line = line.strip()
        if line:
            kind, title = line.split("|", 1)
            wanted.append((kind.strip().upper(), title.strip()))
    metas = {c["title"]: c for c in info([t for _, t in wanted], 1600)}
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, (kind, title) in enumerate(wanted):
        c = metas.get(title)
        if not c:
            print(f"missing: {title}", flush=True)
            continue
        reason = acceptable(c)
        if reason:
            print(f"rejected {title}: {reason}", flush=True)
            continue
        im = Image.open(io.BytesIO(download(c["url"])))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1600, 1600))
        name = f"{kind.lower()}-{i:02d}.jpg"
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)  # no EXIF/GPS kept
        (out / name).write_bytes(buf.getvalue())
        manifest.append(
            {
                "file": name,
                "kind": kind,
                "title": c["title"].removeprefix("File:"),
                "author": c["author"][:120],
                "licence": c["licence"],
                "licence_url": c["licence_url"],
                "source": c["page"],
                "changes": "resized to 1600 px and re-encoded; metadata removed",
                "width": im.width,
                "height": im.height,
            }
        )
        time.sleep(0.3)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(manifest)} photos written", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    target = Path(sys.argv[2])
    if mode == "survey":
        survey(target)
    else:
        fetch(os.environ["PHOTOS"], target)
