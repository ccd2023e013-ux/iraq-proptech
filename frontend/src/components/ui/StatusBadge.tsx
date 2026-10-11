import type { ReactNode } from "react";

export type BadgeTone = "success" | "warning" | "danger" | "neutral";

const TONES: Record<BadgeTone, string> = {
  success: "bg-success/10 text-success ring-success/20",
  warning: "bg-warning/10 text-warning ring-warning/20",
  danger: "bg-danger/10 text-danger ring-danger/20",
  neutral: "bg-fill text-ink-2 ring-hairline",
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
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-tag)] px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      <span aria-hidden className={`size-1.5 rounded-full ${DOTS[tone]}`} />
      {children}
    </span>
  );
}
