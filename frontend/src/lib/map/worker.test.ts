import { describe, expect, it } from "vitest";

import { maplibreWorkerUrl } from "./worker";

describe("maplibre worker URL", () => {
  it("is a same-origin, versioned path", () => {
    expect(maplibreWorkerUrl("6.13.0")).toBe("/maplibre/maplibre-gl-worker-6.13.0.mjs");
    expect(maplibreWorkerUrl("6.14.0-pre.1")).toBe("/maplibre/maplibre-gl-worker-6.14.0-pre.1.mjs");
  });

  it("rejects anything that is not a version", () => {
    for (const bad of ["", "6", "../../evil", "6.13.0/../x", "https://cdn.example/6.13.0"]) {
      expect(() => maplibreWorkerUrl(bad)).toThrow();
    }
  });
});
