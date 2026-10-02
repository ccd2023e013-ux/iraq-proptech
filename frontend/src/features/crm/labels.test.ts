import { describe, expect, it } from "vitest";

import { fromLocalInput, statusName, toLocalInput } from "./labels";

const statuses = [
  {
    code: "NEW",
    name_ar: "جديد",
    name_en: "New",
    sort_order: 0,
    is_terminal: false,
    is_won: false,
    is_active: true,
    is_system: true,
  },
];

describe("crm labels", () => {
  it("names statuses per locale and falls back to the code", () => {
    expect(statusName(statuses, "NEW", "ar")).toBe("جديد");
    expect(statusName(statuses, "NEW", "en")).toBe("New");
    expect(statusName(statuses, "CUSTOM", "en")).toBe("CUSTOM");
  });

  it("round-trips datetime-local values", () => {
    const iso = "2026-10-05T09:30:00.000Z";
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
    expect(fromLocalInput("")).toBeNull();
    expect(toLocalInput(null)).toBe("");
    expect(toLocalInput("garbage")).toBe("");
  });
});
