import type { ReactNode } from "react";

/** Centered card layout shared by the sign-in / sign-up / recovery pages. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-[var(--radius-card)] border border-sand-200 bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-2xl font-bold text-brand-900">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-sand-500">{subtitle}</p>}
        <div className="mt-6">{children}</div>
      </div>
      {footer && <div className="mt-4 text-center text-sm text-sand-700">{footer}</div>}
    </div>
  );
}
