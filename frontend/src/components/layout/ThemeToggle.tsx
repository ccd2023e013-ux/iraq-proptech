"use client";

import { useState } from "react";

import { THEME_COOKIE, type ThemeChoice, nextTheme } from "@/lib/theme";

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/** Applies a theme instantly (no reload) and remembers it in a cookie the server reads. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  document.cookie = `${THEME_COOKIE}=${choice}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
}

const ICONS: Record<ThemeChoice, string> = {
  system: "M12 3a9 9 0 1 0 0 18V3Z",
  light:
    "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0-5v3m0 14v3M2 12h3m14 0h3M4.9 4.9l2.1 2.1m10 10 2.1 2.1m0-14.2-2.1 2.1m-10 10-2.1 2.1",
  dark: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z",
};

export function ThemeToggle({
  initial,
  labels,
}: {
  initial: ThemeChoice;
  labels: Record<ThemeChoice, string>;
}) {
  const [choice, setChoice] = useState<ThemeChoice>(initial);
  const next = nextTheme(choice);
  return (
    <button
      type="button"
      onClick={() => {
        applyTheme(next);
        setChoice(next);
      }}
      title={labels[choice]}
      aria-label={labels[choice]}
      data-theme-choice={choice}
      className="grid size-9 place-items-center rounded-full text-ink-2 transition hover:bg-fill hover:text-ink"
    >
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        className="size-[18px]"
        fill={choice === "light" ? "none" : "currentColor"}
        stroke="currentColor"
        strokeWidth={choice === "light" ? 1.8 : 0}
        strokeLinecap="round"
      >
        {choice === "system" && <circle cx="12" cy="12" r="9" fill="none" strokeWidth={1.8} />}
        <path d={ICONS[choice]} />
      </svg>
    </button>
  );
}
