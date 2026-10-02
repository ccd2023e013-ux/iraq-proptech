import { describe, expect, it } from "vitest";

import ar from "./dictionaries/ar";
import en from "./dictionaries/en";
import { directionOf, resolveLocale } from "./config";

function keyPaths(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keyPaths(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("i18n", () => {
  it("defaults to Arabic and RTL", () => {
    expect(resolveLocale(undefined)).toBe("ar");
    expect(resolveLocale("fr")).toBe("ar");
    expect(directionOf("ar")).toBe("rtl");
    expect(directionOf("en")).toBe("ltr");
  });

  it("English provides exactly the Arabic keys", () => {
    expect(keyPaths(en).sort()).toEqual(keyPaths(ar).sort());
  });

  it("has no empty translations", () => {
    for (const dict of [ar, en]) {
      const values = keyPaths(dict).map((path) =>
        path.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], dict),
      );
      expect(values.every((v) => typeof v === "string" && v.trim().length > 0)).toBe(true);
    }
  });
});
