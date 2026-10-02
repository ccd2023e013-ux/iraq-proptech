import type { Locale } from "./config";
import ar, { type Dictionary } from "./dictionaries/ar";
import en from "./dictionaries/en";

const dictionaries: Record<Locale, Dictionary> = { ar, en };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale];
}

/** Map a stable API error code to a friendly, localized message. */
export function errorMessage(dict: Dictionary, code: string): string {
  const messages = dict.errors as Record<string, string>;
  return messages[code] ?? dict.errors.UNKNOWN;
}

export type { Dictionary };
