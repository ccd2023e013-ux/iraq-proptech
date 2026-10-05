import { describe, expect, it } from "vitest";

import { CITIES, RIVERS, VIEW, project, smoothPath } from "./riverGeometry";

describe("hero river geometry", () => {
  it("projects every city and river point inside the view box", () => {
    const points = [...CITIES.map((c) => c.at), ...Object.values(RIVERS).flat()];
    for (const pt of points) {
      const [x, y] = project(pt);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(VIEW.width);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(VIEW.height);
    }
  });

  it("keeps geography: Basra south-east of Baghdad, Mosul north", () => {
    const [bx, by] = project([47.81, 30.51]);
    const [gx, gy] = project([44.37, 33.31]);
    const [, my] = project([43.13, 36.34]);
    expect(bx).toBeGreaterThan(gx);
    expect(by).toBeGreaterThan(gy);
    expect(my).toBeLessThan(gy);
  });

  it("builds a smooth path that starts at the first point", () => {
    const d = smoothPath(RIVERS.shatt);
    const [x, y] = project(RIVERS.shatt[0]!);
    expect(d.startsWith(`M${x} ${y}`)).toBe(true);
    expect(d.match(/C/g)).toHaveLength(RIVERS.shatt.length - 1);
  });
});
