import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

type Tone = "info" | "success" | "warning" | "error";

const TONES: Record<Tone, { box: string; icon: IconName; mark: string }> = {
  info: { box: "bg-fill", icon: "info", mark: "text-ink-2" },
  success: { box: "bg-accent-tint", icon: "check", mark: "text-accent" },
  warning: { box: "bg-gold-100", icon: "alert", mark: "text-gold-700" },
  error: { box: "bg-danger/10", icon: "alert", mark: "text-danger" },
};

/** A calm, inline message: an icon for tone, plain words, no shouting. */
export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
}) {
  const t = TONES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`fade-in flex gap-3 rounded-[var(--radius-control)] px-4 py-3 text-sm text-ink ${t.box}`}
    >
      <Icon name={t.icon} className={`mt-0.5 size-[18px] shrink-0 ${t.mark}`} />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? "mt-0.5 text-ink-2" : ""}>{children}</div>}
      </div>
    </div>
  );
}
