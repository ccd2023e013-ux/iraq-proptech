import type { CSSProperties } from "react";

/** Placeholder block shown while content loads (shimmer is static under reduced motion). */
export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return (
    <div
      aria-hidden
      style={style}
      className={`skeleton rounded-[var(--radius-control)] ${className}`}
    />
  );
}

export function CardSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-3">
      <Skeleton className="aspect-[4/3] w-full rounded-[var(--radius-card)]" />
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}
