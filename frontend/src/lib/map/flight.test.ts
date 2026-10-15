import { describe, expect, it } from "vitest";

import { cameraAt, constructionAt, offsetMetres, plotRing, presetPath } from "./flight";

describe("drone flight paths", () => {
  it("starts and ends exactly on the first and last keyframes", () => {
    const path = presetPath("approach", 47.8, 30.5);
    expect(cameraAt(path, 0)).toEqual(path[0]);
    expect(cameraAt(path, 1)).toEqual(path[path.length - 1]);
  });

  it("orbits a full turn in one direction", () => {
    const path = presetPath("orbit", 47.8, 30.5);
    const bearings = [0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => cameraAt(path, t, true).bearing);
    for (let i = 1; i < bearings.length; i++)
      expect(bearings[i]!).toBeGreaterThanOrEqual(bearings[i - 1]!);
    expect(bearings[bearings.length - 1]).toBe(360);
    expect(cameraAt(path, 0.5, true).bearing).toBeCloseTo(180, 5); // constant pace
  });

  it("takes the short way between other bearings", () => {
    const path = [
      { lon: 0, lat: 0, zoom: 15, pitch: 0, bearing: 350 },
      { lon: 0, lat: 0, zoom: 15, pitch: 0, bearing: 10 },
    ];
    const mid = cameraAt(path, 0.5).bearing;
    expect(mid).toBeGreaterThan(350);
    expect(mid).toBeLessThanOrEqual(360);
  });

  it("raises the camera with altitude (lower zoom), within limits", () => {
    const low = presetPath("reveal", 47.8, 30.5, 0)[0]!.zoom;
    const high = presetPath("reveal", 47.8, 30.5, 1.5)[0]!.zoom;
    expect(high).toBeLessThan(low);
    expect(presetPath("reveal", 47.8, 30.5, -9)[0]!.zoom).toBeLessThanOrEqual(19);
  });

  it("measures offsets and plots in metres", () => {
    const [lon, lat] = offsetMetres(47.8, 30.5, 0, 1113.2);
    expect(lon).toBe(47.8);
    expect(lat).toBeCloseTo(30.51, 3);
    const ring = plotRing(47.8, 30.5, 400);
    expect(ring).toHaveLength(5);
    expect(ring[0]).toEqual(ring[4]);
  });

  it("raises the building through its stages to the final height", () => {
    expect(constructionAt(0.05, 12)).toMatchObject({ stage: "site", height: 0 });
    expect(constructionAt(0.2, 12).stage).toBe("foundations");
    const mid = constructionAt(0.5, 12);
    expect(mid.stage).toBe("structure");
    expect(mid.height).toBeGreaterThan(0.8);
    expect(mid.height).toBeLessThan(12);
    expect(constructionAt(1, 12)).toMatchObject({ stage: "complete", height: 12 });
  });
});
