import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDictionary } from "@/i18n";

import { HeroSearch } from "./HeroSearch";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const ar = getDictionary("ar");

afterEach(() => push.mockReset());

describe("HeroSearch", () => {
  it("submits keyword and purpose to the search page", () => {
    render(<HeroSearch dict={ar} />);
    fireEvent.click(screen.getByRole("radio", { name: ar.listing.purposes.RENT }));
    fireEvent.change(screen.getByLabelText(ar.search.keyword), {
      target: { value: "  شقة في العشار " },
    });
    fireEvent.click(screen.getByRole("button", { name: ar.landing.heroCta }));
    expect(push).toHaveBeenCalledTimes(1);
    const url = new URL(push.mock.calls[0][0], "http://x");
    expect(url.pathname).toBe("/properties");
    expect(url.searchParams.get("q")).toBe("شقة في العشار");
    expect(url.searchParams.get("purpose")).toBe("RENT");
  });

  it("defaults to sale and omits an empty keyword", () => {
    render(<HeroSearch dict={ar} />);
    fireEvent.click(screen.getByRole("button", { name: ar.landing.heroCta }));
    const url = new URL(push.mock.calls[0][0], "http://x");
    expect(url.searchParams.get("purpose")).toBe("SALE");
    expect(url.searchParams.has("q")).toBe(false);
  });
});
