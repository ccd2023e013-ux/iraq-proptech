import { describe, expect, it } from "vitest";

import { NEAR_RADIUS_KM, nearQuery } from "./NearYou";

describe("properties near you", () => {
  it("searches nearest-first within the radius, rounding the position", () => {
    const q = new URLSearchParams(nearQuery(30.508123456, 47.783987654));
    expect(q.get("near_lat")).toBe("30.50812");
    expect(q.get("near_lon")).toBe("47.78399");
    expect(q.get("radius_km")).toBe(String(NEAR_RADIUS_KM));
    expect(q.get("sort")).toBe("distance");
    expect(q.get("page_size")).toBe("4");
  });
});
