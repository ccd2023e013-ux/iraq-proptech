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
      className="h-9 rounded-full px-3 text-sm font-medium text-ink-2 transition hover:bg-fill hover:text-ink disabled:opacity-50"
    >
      {label}
    </button>
  );
}
