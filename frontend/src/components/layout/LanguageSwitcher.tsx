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
      className="rounded-lg border border-sand-200 px-3 py-1.5 text-sm font-medium text-sand-700 transition hover:border-brand-300 hover:text-brand-700 disabled:opacity-50"
    >
      {label}
    </button>
  );
}
