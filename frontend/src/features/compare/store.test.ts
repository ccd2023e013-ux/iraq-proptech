import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_COMPARE, clearCompare, onCompareChange, readCompare, toggleCompare } from "./store";

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("compare selection", () => {
  it("toggles ids and keeps at most four (oldest dropped)", () => {
    let ids: string[] = [];
    for (const id of ["a", "b", "c", "d", "e"]) ids = toggleCompare(id, ids);
    expect(ids).toEqual(["b", "c", "d", "e"]);
    expect(ids).toHaveLength(MAX_COMPARE);
    expect(readCompare()).toEqual(ids);
    expect(toggleCompare("c", ids)).toEqual(["b", "d", "e"]);
  });

  it("notifies listeners and clears", () => {
    const seen: string[][] = [];
    const off = onCompareChange((ids) => seen.push(ids));
    toggleCompare("x", []);
    clearCompare();
    off();
    toggleCompare("y", []);
    expect(seen).toEqual([["x"], []]);
  });

  it("survives broken or blocked storage", () => {
    window.localStorage.setItem("compare:ids", "{not json");
    expect(readCompare()).toEqual([]);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readCompare()).toEqual([]);
  });
});
