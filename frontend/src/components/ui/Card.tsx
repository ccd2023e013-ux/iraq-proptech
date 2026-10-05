import type { ReactNode } from "react";

/**
 * A quiet surface for grouped content. Hierarchy comes from spacing and type,
 * not borders: a soft elevation in light mode, a lifted surface in dark mode.
 */
export function Card({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-[var(--radius-card)] bg-surface p-5 shadow-soft ring-1 ring-hairline sm:p-6 ${className}`}
    >
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-1 text-sm text-ink-3">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
