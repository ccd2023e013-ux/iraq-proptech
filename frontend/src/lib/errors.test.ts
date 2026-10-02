import { describe, expect, it } from "vitest";

import { getDictionary } from "@/i18n";
import { ApiError } from "@/lib/api/client";

import { describeError } from "./errors";

const ar = getDictionary("ar");

describe("describeError", () => {
  it("lists every password policy problem", () => {
    const error = new ApiError("WEAK_PASSWORD", "weak", 422, undefined, [
      "PASSWORD_TOO_SHORT",
      "PASSWORD_TOO_COMMON",
    ]);
    const text = describeError(ar, error);
    expect(text).toContain(ar.errors.PASSWORD_TOO_SHORT);
    expect(text).toContain(ar.errors.PASSWORD_TOO_COMMON);
  });

  it("maps known codes and falls back for unknown ones", () => {
    expect(describeError(ar, new ApiError("INVALID_CREDENTIALS", "x", 401))).toBe(
      ar.errors.INVALID_CREDENTIALS,
    );
    expect(describeError(ar, new ApiError("SOMETHING_NEW", "x", 400))).toBe(ar.errors.UNKNOWN);
    expect(describeError(ar, new Error("boom"))).toBe(ar.errors.UNKNOWN);
  });
});
