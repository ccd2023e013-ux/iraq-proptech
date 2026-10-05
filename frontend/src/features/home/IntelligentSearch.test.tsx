import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getDictionary } from "@/i18n";

import { IntelligentSearch, searchDestination } from "./IntelligentSearch";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const en = getDictionary("en");

describe("hero search destination", () => {
  it("includes every chosen filter", () => {
    const url = new URL(
      searchDestination({ ai: false, q: "villa", purpose: "RENT", cityId: "c1", type: "VILLA" }),
      "http://x",
    );
    expect(url.pathname).toBe("/properties");
    expect(url.searchParams.get("q")).toBe("villa");
    expect(url.searchParams.get("purpose")).toBe("RENT");
    expect(url.searchParams.get("city_id")).toBe("c1");
    expect(url.searchParams.getAll("property_types")).toEqual(["VILLA"]);
  });

  it("AI search hands the sentence to natural-language search", () => {
    expect(
      searchDestination({
        ai: true,
        q: "بيت للبيع في البصرة",
        purpose: "SALE",
        cityId: "",
        type: "",
      }),
    ).toBe(`/search/smart?q=${encodeURIComponent("بيت للبيع في البصرة")}`);
  });
});

describe("IntelligentSearch", () => {
  it("submits a natural-language query when AI search is on", () => {
    render(<IntelligentSearch dict={en} cities={[]} types={[]} />);
    fireEvent.click(screen.getByLabelText(en.homeV2.aiToggle));
    fireEvent.change(screen.getByLabelText(en.homeV2.aiPlaceholder), {
      target: { value: "house for sale in Basra" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.homeV2.search }));
    expect(push).toHaveBeenCalledWith("/search/smart?q=house%20for%20sale%20in%20Basra");
  });
});
