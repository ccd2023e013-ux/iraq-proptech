import type { ReactNode } from "react";

/**
 * Re-mounted on every navigation: a short fade-and-rise that tells the eye the
 * page changed (instant under reduced motion).
 */
export default function Template({ children }: { children: ReactNode }) {
  return <div className="animate-enter">{children}</div>;
}
