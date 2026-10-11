import { describe, expect, it } from "vitest";

import { tagLabel } from "./bubbles";
import {
  cameraDuration,
  cubicBezier,
  easeStandard,
  focusZoom,
  openAreaOffset,
  placeTags,
} from "./camera";

describe("map camera", () => {
  it("eases like the CSS curve: monotonic from 0 to 1, fast start", () => {
    expect(easeStandard(0)).toBe(0);
    expect(easeStandard(1)).toBe(1);
    let last = 0;
    for (let i = 1; i <= 20; i++) {
      const v = easeStandard(i / 20);
      expect(v).toBeGreaterThanOrEqual(last - 1e-9);
      last = v;
    }
    expect(easeStandard(0.25)).toBeGreaterThan(0.5); // most of the move happens early
    const linear = cubicBezier(0.25, 0.25, 0.75, 0.75);
    expect(linear(0.4)).toBeCloseTo(0.4, 3);
  });

  it("changes zoom by at most two levels and never past 15 when focusing", () => {
    expect(focusZoom(11)).toBe(13);
    expect(focusZoom(13.6)).toBe(15);
    expect(focusZoom(14.2)).toBe(14.2);
    expect(focusZoom(17)).toBe(17);
  });

  it("offsets towards the open side of the map, mirrored in RTL", () => {
    expect(openAreaOffset(400, 0, false)).toEqual([200, 0]);
    expect(openAreaOffset(400, 0, true)).toEqual([-200, 0]);
    expect(openAreaOffset(0, 180, false)).toEqual([0, -90]);
  });

  it("makes every move instant under reduced motion", () => {
    expect(cameraDuration(true)).toBe(0);
    expect(cameraDuration(false)).toBe(800);
  });

  it("places tags without overlap, keeping pinned ones and the limit", () => {
    const box = (id: string, x: number, pinned = false) => ({
      id,
      x,
      y: 0,
      width: 60,
      height: 24,
      pinned,
    });
    const shown = placeTags([box("a", 0), box("b", 30), box("c", 120), box("d", 40, true)], 10);
    expect(shown.has("d")).toBe(true); // pinned wins its spot
    expect(shown.has("a")).toBe(false); // overlaps d
    expect(shown.has("b")).toBe(false);
    expect(shown.has("c")).toBe(true);
    expect(placeTags([box("a", 0), box("b", 100), box("c", 200)], 2).size).toBe(2);
  });
});

describe("map tag labels", () => {
  it("writes Arabic prices in Arabic with Latin digits", () => {
    expect(tagLabel("269000000", "IQD", false, null, "ar")).toBe("269 مليون د.ع");
    expect(tagLabel("1530000", "IQD", false, "MONTHLY", "ar")).toBe("1.5 مليون د.ع/شهر");
    expect(tagLabel("1250000000", "IQD", false, null, "ar")).toBe("1.3 مليار د.ع");
    expect(tagLabel("165000", "USD", false, null, "ar")).toBe("165 ألف دولار");
    expect(tagLabel("950", "USD", false, "MONTHLY", "ar")).toBe("950 دولار/شهر");
  });

  it("keeps English compact", () => {
    expect(tagLabel("357000", "USD", false, null, "en")).toBe("$357K");
    expect(tagLabel("1530000", "IQD", false, "MONTHLY", "en")).toBe("1.5M IQD/mo");
    expect(tagLabel(null, "IQD", false, null, "en")).toBe("—");
    expect(tagLabel("5000", "IQD", true, null, "ar")).toBe("—");
  });
});
