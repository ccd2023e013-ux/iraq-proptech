import { describe, expect, it } from "vitest";

import { nextTheme, parseTheme } from "./theme";

describe("theme choice", () => {
  it("defaults to the system preference", () => {
    expect(parseTheme(undefined)).toBe("system");
    expect(parseTheme("purple")).toBe("system");
    expect(parseTheme("dark")).toBe("dark");
  });
  it("cycles system → light → dark → system", () => {
    expect(nextTheme("system")).toBe("light");
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("system");
  });
});
