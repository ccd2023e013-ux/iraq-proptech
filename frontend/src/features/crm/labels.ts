import type { Locale } from "@/i18n/config";
import type { LeadStatus } from "@/types/crm";

export function statusName(statuses: LeadStatus[], code: string, locale: Locale): string {
  const s = statuses.find((x) => x.code === code);
  return s ? (locale === "ar" ? s.name_ar : s.name_en) : code;
}

/** Value for <input type="datetime-local"> in the browser's local time. */
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local value → ISO with timezone (null when empty). */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function formatDateTime(iso: string | null, locale: Locale): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}
