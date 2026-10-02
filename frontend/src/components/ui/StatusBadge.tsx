import type { ReactNode } from "react";

export type BadgeTone = "success" | "warning" | "danger" | "neutral";

const TONES: Record<BadgeTone, string> = {
  success: "bg-emerald-50 text-success ring-emerald-200",
  warning: "bg-amber-50 text-warning ring-amber-200",
  danger: "bg-red-50 text-danger ring-red-200",
  neutral: "bg-sand-100 text-sand-700 ring-sand-200",
};

const DOTS: Record<BadgeTone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-sand-500",
};

export function StatusBadge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  return (
    <span
      data-tone={tone}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      <span aria-hidden className={`size-1.5 rounded-full ${DOTS[tone]}`} />
      {children}
    </span>
  );
}
