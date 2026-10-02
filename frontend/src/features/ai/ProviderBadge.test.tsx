import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SafeImage } from "@/components/ui/SafeImage";
import { getDictionary } from "@/i18n";

import { ProviderBadge, providerLabel } from "./ProviderBadge";

const ar = getDictionary("ar");
const en = getDictionary("en");

describe("AI provider labelling", () => {
  it("never presents the mock provider as a real model", () => {
    expect(providerLabel(en, "mock")).toMatch(/simulation/i);
    expect(providerLabel(ar, "mock")).toContain("محاكاة");
    expect(providerLabel(en, "platform")).toMatch(/statistical/i);
    expect(providerLabel(en, "claude", "claude-x")).toContain("claude");
  });

  it("renders the badge with its provider", () => {
    render(<ProviderBadge dict={ar} provider="mock" />);
    expect(screen.getByText(ar.ai.providerMock)).toHaveAttribute("data-ai-provider", "mock");
  });
});

describe("SafeImage", () => {
  it("replaces a broken image with a placeholder", () => {
    const { container } = render(
      <SafeImage src="/missing.webp" alt="" fallbackLabel="لا توجد صورة" />,
    );
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    fireEvent.error(img as HTMLImageElement);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("img")).toHaveTextContent("لا توجد صورة");
  });
});
