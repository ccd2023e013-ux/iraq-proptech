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
    <section className={`surface-1 rounded-[var(--radius-card)] p-5 sm:p-6 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && (
              <h2 className="font-display text-[17px] font-semibold tracking-tight text-ink">
                {title}
              </h2>
            )}
            {description && <p className="mt-1 text-sm text-ink-3">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
