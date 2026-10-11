"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { LOCALE_COOKIE, type Locale } from "@/i18n/config";

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

export function LanguageSwitcher({ current, label }: { current: Locale; label: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const next: Locale = current === "ar" ? "en" : "ar";

  return (
    <button
      type="button"
      lang={next}
      disabled={pending}
      onClick={() => {
        document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
        startTransition(() => router.refresh());
      }}
      aria-label={label}
      className="press h-9 rounded-[var(--radius-control)] px-2.5 text-sm font-medium whitespace-nowrap text-ink-2 hover:bg-fill hover:text-ink disabled:opacity-50 sm:px-3"
    >
      {/* Short form on phones so the header never wraps or overflows. */}
      <span aria-hidden className="sm:hidden">
        {next === "en" ? "EN" : "ع"}
      </span>
      <span aria-hidden className="hidden sm:inline">
        {label}
      </span>
    </button>
  );
}
