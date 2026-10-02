import { describe, expect, it } from "vitest";

import { guardDecision, isProtectedPath, safeNextPath } from "./routing";

describe("safeNextPath", () => {
  it.each([
    ["/dashboard/properties?page=2", "/dashboard/properties?page=2"],
    ["/account#security", "/account#security"],
  ])("keeps same-site path %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });

  it.each([
    "https://evil.example/phish",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "dashboard",
    "",
    null,
    "/\u0000x",
  ])("rejects open redirect %s", (input) => {
    expect(safeNextPath(input as string | null)).toBe("/dashboard");
  });
});

describe("guardDecision", () => {
  it("lets public pages through", () => {
    expect(guardDecision("/", "", false, false)).toEqual({ action: "allow" });
    expect(isProtectedPath("/dashboardx")).toBe(false);
  });

  it("sends anonymous users to login with a return path", () => {
    expect(guardDecision("/account", "?tab=security", false, false)).toEqual({
      action: "login",
      next: "/account?tab=security",
    });
  });

  it("renews an expired access cookie when a refresh cookie exists", () => {
    expect(guardDecision("/dashboard", "", false, true)).toEqual({
      action: "refresh",
      next: "/dashboard",
    });
  });

  it("allows signed-in users", () => {
    expect(guardDecision("/admin/users", "", true, true)).toEqual({ action: "allow" });
  });
});
