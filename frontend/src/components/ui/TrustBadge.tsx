import type { ReactNode } from "react";

/**
 * What kind of statement the user is looking at. Used everywhere data is not a
 * plain declared fact: demo content, estimates, AI output, simulations.
 */
export type TrustKind = "fact" | "observed" | "source" | "estimate" | "ai" | "simulation" | "demo";

const STYLES: Record<TrustKind, string> = {
  fact: "bg-fill text-ink-2",
  observed: "bg-accent-tint text-accent",
  source: "bg-accent-tint text-accent",
  estimate: "bg-gold-100 text-gold-700",
  ai: "bg-ink text-surface",
  simulation: "bg-gold-100 text-gold-700",
  demo: "bg-gold-500 text-[#1d1405]", // dark text on gold: 6.9:1
};

export function TrustBadge({ kind, children }: { kind: TrustKind; children: ReactNode }) {
  return (
    <span
      data-trust={kind}
      className={`inline-flex items-center rounded-[var(--radius-tag)] px-2 py-0.5 text-[11px] font-semibold leading-5 ${STYLES[kind]}`}
    >
      {children}
    </span>
  );
}
