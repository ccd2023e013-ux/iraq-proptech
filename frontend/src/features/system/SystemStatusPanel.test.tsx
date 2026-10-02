import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { getDictionary } from "@/i18n";

import { SystemStatusPanel } from "./SystemStatusPanel";

const ar = getDictionary("ar");
const en = getDictionary("en");

describe("SystemStatusPanel", () => {
  it("shows every dependency with an Arabic label and tone", () => {
    render(
      <SystemStatusPanel
        dict={ar}
        result={{
          kind: "ok",
          readiness: {
            status: "degraded",
            database: { status: "ok" },
            postgis: { status: "ok", detail: "3.4.2" },
            redis: { status: "unavailable" },
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "حالة النظام" })).toBeInTheDocument();
    const redisRow = screen.getByText(ar.status.redis).closest("div")!;
    expect(within(redisRow).getByText("غير متاح")).toBeInTheDocument();
    const apiRow = screen.getByText(ar.status.api).closest("div")!;
    expect(within(apiRow).getByText("يعمل جزئياً").closest("[data-tone]")).toHaveAttribute(
      "data-tone",
      "warning",
    );
  });

  it("explains a missing API URL instead of failing silently", () => {
    render(<SystemStatusPanel dict={en} result={{ kind: "error", code: "API_NOT_CONFIGURED" }} />);
    expect(screen.getByText("API URL is not configured")).toBeInTheDocument();
  });

  it("maps API error codes to friendly messages", () => {
    render(<SystemStatusPanel dict={ar} result={{ kind: "error", code: "NETWORK_ERROR" }} />);
    expect(screen.getByText(ar.errors.NETWORK_ERROR)).toBeInTheDocument();
  });
});
