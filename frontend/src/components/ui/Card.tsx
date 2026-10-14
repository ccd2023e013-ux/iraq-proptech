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
    <section className={`panel p-6 sm:p-8 ${className}`}>
      {(title || actions) && (
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && <h2 className="title text-ink">{title}</h2>}
            {description && <p className="meta mt-1">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
