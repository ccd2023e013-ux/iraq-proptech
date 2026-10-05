import type { Dictionary } from "@/i18n";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
export const PASSWORD_MIN = 10;

export type FieldErrors = Partial<Record<"email" | "password" | "full_name", string>>;

/** Client-side checks mirroring the API rules; the server remains the authority. */
export function validateAuth(
  dict: Dictionary,
  values: { email?: string; password?: string; full_name?: string },
  mode: "login" | "register" | "reset" | "forgot",
): FieldErrors {
  const a = dict.auth;
  const errors: FieldErrors = {};
  if (values.email !== undefined) {
    const email = values.email.trim();
    if (!email) errors.email = a.errRequired;
    else if (!EMAIL.test(email)) errors.email = a.errEmail;
  }
  if (values.password !== undefined && mode !== "forgot") {
    if (!values.password) errors.password = a.errRequired;
    else if (mode !== "login" && values.password.length < PASSWORD_MIN)
      errors.password = a.errPasswordShort;
  }
  if (values.full_name !== undefined && values.full_name.trim().length < 2) {
    errors.full_name = a.errNameShort;
  }
  return errors;
}
