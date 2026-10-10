import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getDictionary } from "@/i18n";
import type { Bbox, LonLat } from "@/lib/map/geo";
import { resolveMapConfig } from "@/lib/map/provider";

import { MapSearch } from "./MapSearch";
import type { PropertyMapProps } from "./PropertyMap";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/map",
}));
// Map data requests never settle: these tests are about URL navigation only.
vi.mock("@/lib/api/client", () => ({ apiFetch: vi.fn(() => new Promise(() => {})) }));

let map: PropertyMapProps;
vi.mock("./PropertyMap", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./PropertyMap")>()),
  PropertyMap: (props: PropertyMapProps) => {
    map = props;
    return null;
  },
}));

const en = getDictionary("en");
const BASRA: Bbox = [47.7, 30.4, 47.92, 30.62];
const PANNED: Bbox = [47.72, 30.41, 47.94, 30.63];

function renderMap() {
  return render(
    <MapSearch
      config={resolveMapConfig({})}
      dict={en}
      locale="en"
      params={{ bbox: BASRA.join(",") }}
      items={[]}
      total={0}
      boundaries={null}
      initialBbox={BASRA}
    />,
  );
}

const lastUrl = () => new URL(String(replace.mock.lastCall?.[0]), "http://x");

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  replace.mockReset();
});

describe("MapSearch viewport and draw-area navigation", () => {
  it("follows the map: a pan navigates to the new bbox after the debounce", () => {
    renderMap();
    act(() => map.onViewportChange(PANNED, 12));
    expect(replace).not.toHaveBeenCalled();
    act(() => void vi.advanceTimersByTime(500));
    expect(replace).toHaveBeenCalledTimes(1);
    expect(lastUrl().searchParams.get("bbox")).toBe(PANNED.map((v) => v.toFixed(5)).join(","));
  });

  it("ignores a pan that ends after 'Draw area' (stale handler from before the click)", () => {
    renderMap();
    // The handler the map holds before the click (a pan's inertia can end, and
    // call it, before React has re-rendered with the drawing state).
    const staleOnViewportChange = map.onViewportChange;
    fireEvent.click(screen.getByTestId("draw-area"));
    act(() => staleOnViewportChange(PANNED, 12));
    act(() => void vi.advanceTimersByTime(2_000));
    expect(replace).not.toHaveBeenCalled();
  });

  it("drops a pending pan when drawing starts, then applies only the polygon", () => {
    renderMap();
    // Pan, then click "Draw area" inside the 450 ms debounce window.
    act(() => map.onViewportChange(PANNED, 12));
    fireEvent.click(screen.getByTestId("draw-area"));
    act(() => void vi.advanceTimersByTime(2_000));
    expect(replace).not.toHaveBeenCalled();

    const points: LonLat[] = [
      [47.76, 30.55],
      [47.86, 30.55],
      [47.81, 30.48],
    ];
    for (const p of points) act(() => map.onDrawPoint(p));
    fireEvent.click(screen.getByTestId("finish-area"));
    act(() => void vi.advanceTimersByTime(2_000));

    expect(replace).toHaveBeenCalledTimes(1);
    const url = lastUrl();
    expect(url.pathname).toBe("/map");
    expect(url.searchParams.get("polygon")).toBe(
      "47.760000,30.550000;47.860000,30.550000;47.810000,30.480000",
    );
    expect(url.searchParams.has("bbox")).toBe(false);
  });
});
