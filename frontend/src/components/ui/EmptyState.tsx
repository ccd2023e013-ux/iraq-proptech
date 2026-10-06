import Link from "next/link";
import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

/**
 * An empty screen is an invitation to act: say what is missing and what to do
 * next. A single quiet glyph on a faint survey grid — no illustrations.
 */
export function EmptyState({
  title,
  body,
  action,
  icon,
  glyph = "search",
}: {
  title: string;
  body?: ReactNode;
  action?: { href: string; label: string };
  /** Custom icon node; otherwise `glyph` from the MAKAN icon set is used. */
  icon?: ReactNode;
  glyph?: IconName;
}) {
  return (
    <div className="reveal relative isolate flex flex-col items-center gap-3 overflow-hidden rounded-[var(--radius-card)] px-6 py-14 text-center">
      <div aria-hidden className="stage-grid absolute inset-0 -z-10" />
      <div
        aria-hidden
        className="surface-1 mb-1 grid size-14 place-items-center rounded-2xl text-ink-2"
      >
        {icon ?? <Icon name={glyph} className="size-6" />}
      </div>
      <p className="font-display text-lg font-semibold tracking-tight text-ink">{title}</p>
      {body && <div className="max-w-md text-sm text-ink-2">{body}</div>}
      {action && (
        <Link
          href={action.href}
          className="press mt-2 inline-flex h-10 items-center rounded-full bg-accent-fill px-5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
