import { describe, expect, it } from "vitest";

import { getDictionary } from "@/i18n";

import { validateAuth } from "./validation";

const ar = getDictionary("ar");
const en = getDictionary("en");

describe("auth form validation", () => {
  it("requires a well-formed email", () => {
    expect(validateAuth(en, { email: "" }, "login").email).toBe(en.auth.errRequired);
    expect(validateAuth(en, { email: "nope" }, "login").email).toBe(en.auth.errEmail);
    expect(validateAuth(en, { email: "a@b.iq" }, "login").email).toBeUndefined();
  });

  it("checks password length only where a new password is chosen", () => {
    expect(validateAuth(en, { password: "short" }, "login").password).toBeUndefined();
    expect(validateAuth(en, { password: "short" }, "register").password).toBe(
      en.auth.errPasswordShort,
    );
    expect(validateAuth(en, { password: "long-enough-pw" }, "reset").password).toBeUndefined();
  });

  it("speaks Arabic in Arabic", () => {
    const errors = validateAuth(ar, { email: "x", password: "", full_name: "" }, "register");
    expect(errors.email).toBe(ar.auth.errEmail);
    expect(errors.password).toBe(ar.auth.errRequired);
    expect(errors.full_name).toBe(ar.auth.errNameShort);
  });
});
