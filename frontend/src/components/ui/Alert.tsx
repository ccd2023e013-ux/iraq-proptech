import type { ReactNode } from "react";

type Tone = "info" | "success" | "warning" | "error";

const TONES: Record<Tone, string> = {
  info: "bg-accent-tint text-ink",
  success: "bg-success/10 text-ink",
  warning: "bg-warning/10 text-ink",
  error: "bg-danger/10 text-ink",
};

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-[var(--radius-control)] px-4 py-3 text-sm ${TONES[tone]}`}
    >
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={title ? "mt-1" : ""}>{children}</div>}
    </div>
  );
}
