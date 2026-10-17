"""Render a bilingual type specimen for every @fontsource package installed in a folder.

Usage: python specimen.py <folder with node_modules> <output folder>
Writes specimen-<family>.png (light) and specimen-<family>-dark.png per family.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])

SAMPLE = """
<div class="d1">البصرة</div>
<div class="d2">Basra, Al-Ashar</div>
<div class="row"><span class="p">269 مليون د.ع</span><span class="p">$165,000</span><span class="p">1.5M IQD/mo</span></div>
<div class="h">بيت للبيع في العشار — ثلاث غرف نوم، ٣٠٠ م²</div>
<div class="h l">House for sale in Al-Ashar — 3 bedrooms, 300 m²</div>
<p dir="rtl">مَكان يقرأ كل عقار في مكانه: ما حوله، وسوقه، وما يُخطّط قربه. الأرقام هنا من إعلانات تجريبية، وليست أسعار سوق حقيقية.</p>
<p>MAKAN reads every property where it is: its surroundings, its market and what is planned nearby. 0123456789</p>
"""


def families() -> list[tuple[str, str, str]]:
    found = []
    for css in sorted(ROOT.glob("node_modules/@fontsource*/*/index.css")):
        text = css.read_text()
        m = re.search(r"font-family:\s*'([^']+)'", text)
        if m:
            found.append((m.group(1), css.as_uri(), css.parent.name))
    return found


def page(name: str, uri: str, dark: bool) -> str:
    bg, ink = ("#0b0f17", "#ede7dc") if dark else ("#f2f3f1", "#0b0f17")
    return f"""<!doctype html><meta charset=utf-8><link rel=stylesheet href="{uri}">
<style>
body{{margin:0;padding:48px;background:{bg};color:{ink};font-family:'{name}';width:1100px}}
.tag{{font:14px system-ui;opacity:.6;margin-bottom:24px}}
.d1{{font-size:120px;line-height:1.1;font-weight:700;direction:rtl;text-align:right}}
.d2{{font-size:72px;line-height:1.1;font-weight:600;letter-spacing:-0.02em}}
.row{{display:flex;gap:40px;margin:28px 0;font-size:40px;font-weight:600;font-variant-numeric:tabular-nums}}
.h{{font-size:30px;font-weight:500;direction:rtl;text-align:right;margin:8px 0}}
.h.l{{direction:ltr;text-align:left}}
p{{font-size:19px;line-height:1.65;font-weight:400;max-width:900px}}
</style><div class=tag>{name}</div>{SAMPLE}"""


def main() -> None:
    fams = families()
    (OUT / "families.txt").write_text("\n".join(f"{n} {p}" for n, _, p in fams))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, uri, pkg in fams:
            for dark in (False, True):
                html = OUT / f"_{pkg}.html"
                html.write_text(page(name, uri, dark))
                pg = browser.new_page(viewport={"width": 1196, "height": 900})
                pg.goto(html.as_uri())
                pg.wait_for_timeout(600)
                suffix = "-dark" if dark else ""
                pg.screenshot(path=str(OUT / f"specimen-{pkg}{suffix}.png"), full_page=True)
                pg.close()
                html.unlink()
        browser.close()


if __name__ == "__main__":
    main()
