import { type Dictionary, errorMessage } from "@/i18n";
import { ApiError } from "@/lib/api/client";

/** Turn any thrown value into a friendly, localized message for the UI. */
export function describeError(dict: Dictionary, error: unknown): string {
  if (!(error instanceof ApiError)) return dict.errors.UNKNOWN;
  if (error.code === "WEAK_PASSWORD" && Array.isArray(error.details) && error.details.length) {
    return error.details.map((code) => errorMessage(dict, String(code))).join(" ");
  }
  return errorMessage(dict, error.code);
}
