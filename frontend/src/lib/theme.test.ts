import { describe, expect, it } from "vitest";

import { nextTheme, parseTheme } from "./theme";

describe("theme choice", () => {
  it("defaults to dark and keeps explicit choices", () => {
    expect(parseTheme(undefined)).toBe("dark");
    expect(parseTheme("purple")).toBe("dark");
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("system")).toBe("system");
  });
  it("cycles dark → light → system → dark", () => {
    expect(nextTheme("dark")).toBe("light");
    expect(nextTheme("light")).toBe("system");
    expect(nextTheme("system")).toBe("dark");
  });
});
