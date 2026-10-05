import Link from "next/link";
import type { ReactNode } from "react";

import { RiverMap } from "@/features/home/RiverMap";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";

/**
 * Two-pane layout for sign-in, sign-up and recovery: the form on a calm
 * surface, and (on large screens) the river map as a quiet brand panel.
 * On phones only the form shows, so nothing pushes it below the fold.
 */
export function AuthShell({
  dict,
  locale,
  title,
  subtitle,
  children,
  footer,
}: {
  dict: Dictionary;
  locale: Locale;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="mx-auto grid min-h-[calc(100dvh-4rem)] max-w-6xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,28rem)_minmax(0,1fr)] lg:gap-16">
      <section className="w-full max-w-md justify-self-center lg:justify-self-start">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-2 text-ink-2">{subtitle}</p>}
        <div className="mt-8 rounded-[var(--radius-card)] bg-surface p-6 shadow-soft ring-1 ring-hairline sm:p-7">
          {children}
        </div>
        {footer && (
          <div className="mt-5 flex flex-col items-center gap-2 text-sm text-ink-2">{footer}</div>
        )}
      </section>
      <aside
        aria-hidden
        className="relative hidden overflow-hidden rounded-[var(--radius-media)] bg-fill p-10 lg:block"
      >
        <p className="font-display text-2xl font-semibold tracking-tight text-ink">
          {dict.auth.sideTitle}
        </p>
        <p className="mt-2 max-w-sm text-ink-2">{dict.auth.sideBody}</p>
        <div className="mx-auto mt-6 max-w-sm">
          <RiverMap locale={locale} counts={{}} caption="" animate={false} />
        </div>
      </aside>
    </div>
  );
}

/** A quiet inline link used under the auth card. */
export function AuthLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="font-medium text-accent underline-offset-4 hover:underline focus-visible:underline"
    >
      {children}
    </Link>
  );
}
