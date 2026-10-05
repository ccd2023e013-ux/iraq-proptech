import Link from "next/link";
import type { ReactNode } from "react";

/** An empty screen is an invitation to act: say what is missing and what to do next. */
export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string;
  body?: ReactNode;
  action?: { href: string; label: string };
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[var(--radius-card)] bg-fill/60 px-6 py-12 text-center">
      {icon && (
        <div aria-hidden className="text-3xl text-ink-3">
          {icon}
        </div>
      )}
      <p className="font-display text-lg font-semibold text-ink">{title}</p>
      {body && <div className="max-w-md text-sm text-ink-2">{body}</div>}
      {action && (
        <Link
          href={action.href}
          className="mt-2 inline-flex h-10 items-center rounded-full bg-accent-fill px-5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
