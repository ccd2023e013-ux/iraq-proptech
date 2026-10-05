import { describe, expect, it } from "vitest";

import { bubbleLabel, parseHex, pillImage, withPriceLabels } from "./bubbles";
import { bboxAround, PLACE_GROUPS, placesAllowed } from "./places";

describe("price bubbles", () => {
  it("formats short, font-safe prices", () => {
    expect(bubbleLabel("357000", "USD", false)).toBe("$357K");
    expect(bubbleLabel("269000000", "IQD", false)).toBe("269M IQD");
    expect(bubbleLabel("1530000", "IQD", false)).toBe("1.5M IQD");
    expect(bubbleLabel("1250000000", "IQD", false)).toBe("1.3B IQD");
    expect(bubbleLabel("950", "USD", false)).toBe("$950");
    expect(bubbleLabel(null, "IQD", false)).toBe("—");
    expect(bubbleLabel("5000", "IQD", true)).toBe("—");
  });

  it("labels points and leaves clusters alone", () => {
    const labelled = withPriceLabels({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [47.8, 30.5] },
          properties: { id: "a", price_amount: "120000", currency: "USD" },
        },
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [47.8, 30.5] },
          properties: { cluster: true, point_count: 4 },
        },
      ],
    });
    expect(labelled.features[0]!.properties).toMatchObject({ price_label: "$120K" });
    expect(labelled.features[1]!.properties).not.toHaveProperty("price_label");
  });

  it("parses theme colours with a fallback", () => {
    expect(parseHex("#fff", [0, 0, 0, 0])).toEqual([255, 255, 255, 255]);
    expect(parseHex(" #12746b ", [0, 0, 0, 0])).toEqual([18, 116, 107, 255]);
    expect(parseHex("rgb(1 2 3)", [9, 9, 9, 9])).toEqual([9, 9, 9, 9]);
  });

  it("rasterises a stretchable pill with transparent corners and an opaque middle", () => {
    const pill = pillImage([255, 255, 255, 255], [0, 0, 0, 255], 2);
    expect(pill.data.length).toBe(pill.width * pill.height * 4);
    const alpha = (x: number, y: number) => pill.data[(y * pill.width + x) * 4 + 3]!;
    expect(alpha(0, 0)).toBe(0); // rounded corner
    expect(alpha(Math.floor(pill.width / 2), Math.floor(pill.height / 2))).toBe(255);
    const [[x1, x2]] = pill.stretchX as [[number, number]];
    expect(x1).toBeLessThan(x2);
    expect(pill.content[0]).toBeLessThan(pill.content[2]);
  });
});

describe("map places", () => {
  it("only loads places for city-sized views", () => {
    expect(placesAllowed(null)).toBe(false);
    expect(placesAllowed([47.7, 30.4, 47.9, 30.6])).toBe(true);
    expect(placesAllowed([38.8, 29.1, 48.6, 37.4])).toBe(false);
  });

  it("builds a box around a point", () => {
    const [w, s, e, n] = bboxAround(47.8, 30.5, 3);
    expect(w).toBeLessThan(47.8);
    expect(e).toBeGreaterThan(47.8);
    expect(n - s).toBeCloseTo(6 / 111, 3);
  });

  it("groups categories the API knows", () => {
    expect(PLACE_GROUPS.flatMap((g) => g.categories)).toContain("HOSPITAL");
  });
});
