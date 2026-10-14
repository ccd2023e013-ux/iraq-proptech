import Link from "next/link";
import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

/**
 * An empty screen is an invitation to act: say what is missing and what to do
 * next, at a size that reads as designed — not a small box lost in the page.
 */
export function EmptyState({
  title,
  body,
  action,
  secondary,
  icon,
  glyph = "search",
  compact = false,
}: {
  title: string;
  body?: ReactNode;
  action?: { href: string; label: string };
  secondary?: { href: string; label: string };
  /** Custom icon node; otherwise `glyph` from the MAKAN icon set is used. */
  icon?: ReactNode;
  glyph?: IconName;
  /** Inside a panel or list (less height). */
  compact?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-start gap-4 rounded-[var(--radius-card)] bg-surface/60 shadow-[inset_0_0_0_1px_var(--hairline)] ${compact ? "px-6 py-8" : "px-8 py-12 md:px-12 md:py-16"}`}
    >
      <span
        aria-hidden
        className="grid size-12 place-items-center rounded-full bg-fill text-spatial"
      >
        {icon ?? <Icon name={glyph} className="size-[22px]" strokeWidth={1.6} />}
      </span>
      <div className="flex max-w-xl flex-col gap-2">
        <p className={`${compact ? "title" : "display-md"} text-ink`}>{title}</p>
        {body && <div className="text-ink-2">{body}</div>}
      </div>
      {(action || secondary) && (
        <div className="mt-2 flex flex-wrap gap-2">
          {action && (
            <Link href={action.href} className="btn btn-primary">
              {action.label}
            </Link>
          )}
          {secondary && (
            <Link href={secondary.href} className="btn btn-secondary">
              {secondary.label}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
