import { describe, expect, it } from "vitest";

import { DEFAULT_FORM, toRequest } from "./VisionStudio";

describe("vision brief", () => {
  it("clamps numbers and trims notes before sending", () => {
    const body = toRequest(
      { ...DEFAULT_FORM, floors: 40, plot_width_m: 2, plot_depth_m: Number.NaN, notes: "  " },
      "abc",
    );
    expect(body.floors).toBe(12);
    expect(body.plot_width_m).toBe(6);
    expect(body.plot_depth_m).toBe(6);
    expect(body.notes).toBeNull();
    expect(body.property_id).toBe("abc");
  });
});
