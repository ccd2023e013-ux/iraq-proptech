import type { ReactNode } from "react";

/**
 * What kind of statement the user is looking at. Used everywhere data is not a
 * plain declared fact: demo content, estimates, AI output, simulations.
 */
export type TrustKind = "fact" | "observed" | "source" | "estimate" | "ai" | "simulation" | "demo";

/* A ledger mark: a small coloured point and the word, not a filled box —
   provenance is stated, not shouted (docs/ART-DIRECTION.md). Demo keeps a
   tinted ground so it is never missed. */
const INK: Record<TrustKind, string> = {
  fact: "text-ink-2",
  observed: "text-accent",
  source: "text-accent",
  estimate: "text-gold-700",
  ai: "text-ink",
  simulation: "text-gold-700",
  demo: "bg-gold-100 text-gold-700 px-1.5",
};
const DOT: Record<TrustKind, string> = {
  fact: "bg-ink-3",
  observed: "bg-accent-fill",
  source: "bg-accent-fill",
  estimate: "bg-gold-500",
  ai: "bg-ink",
  simulation: "bg-gold-500",
  demo: "bg-gold-500",
};

export function TrustBadge({ kind, children }: { kind: TrustKind; children: ReactNode }) {
  return (
    <span
      data-trust={kind}
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-tag)] text-[12.5px] leading-5 font-medium whitespace-nowrap ${INK[kind]}`}
    >
      <span aria-hidden className={`size-1.5 shrink-0 rounded-full ${DOT[kind]}`} />
      {children}
    </span>
  );
}
