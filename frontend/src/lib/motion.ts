import type { CSSProperties } from "react";

/**
 * Stagger index for `.reveal` siblings (45ms apart, capped in CSS at 8 so long
 * lists never feel slow). Under reduced motion the delay is removed.
 */
export function stagger(i: number): CSSProperties {
  return { "--i": i } as CSSProperties;
}
