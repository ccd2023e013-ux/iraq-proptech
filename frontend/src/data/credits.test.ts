import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import credits from "./demo-photo-credits.json";

describe("demo photo credits", () => {
  it("match the backend's photo manifest exactly", () => {
    const backend = JSON.parse(
      readFileSync(resolve(process.cwd(), "../backend/app/demo_photos/manifest.json"), "utf8"),
    );
    expect(credits).toEqual(backend);
  });

  it("credit every photo with author, licence and source", () => {
    for (const c of credits) {
      expect(c.author.trim()).not.toBe("");
      expect(c.licence).toMatch(/^(Public domain|CC0|CC BY(-SA)? \d\.\d)$/);
      expect(c.source).toMatch(
        /^https:\/\/(commons\.wikimedia\.org\/wiki\/File:|www\.flickr\.com\/photos\/)/,
      );
    }
  });
});
