import { describe, expect, it } from "vitest";

import { safeRedirect } from "./types";

describe("safeRedirect", () => {
  it("allows same-site paths only", () => {
    expect(safeRedirect("/billing/demo/abc")).toBe("/billing/demo/abc");
    expect(safeRedirect("//evil.example")).toBeNull();
    expect(safeRedirect("https://evil.example")).toBeNull();
    expect(safeRedirect("/\\evil.example")).toBeNull();
  });
});
