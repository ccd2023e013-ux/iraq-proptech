import { describe, expect, it } from "vitest";

import { availableActions } from "./ListingActions";

describe("availableActions", () => {
  it("offers submission for drafts and rejected listings", () => {
    expect(availableActions({ status: "DRAFT", purpose: "SALE" })).toEqual(["submit", "archive"]);
    expect(availableActions({ status: "REJECTED", purpose: "RENT" })).toContain("submit");
  });

  it("offers sold for sales and rented for rentals only", () => {
    expect(availableActions({ status: "APPROVED", purpose: "SALE" })).toEqual([
      "unpublish",
      "archive",
      "mark-sold",
    ]);
    expect(availableActions({ status: "APPROVED", purpose: "RAHN" })).toEqual([
      "unpublish",
      "archive",
      "mark-rented",
    ]);
  });

  it("offers nothing for suspended listings (moderation lock)", () => {
    expect(availableActions({ status: "SUSPENDED", purpose: "SALE" })).toEqual([]);
  });
});
