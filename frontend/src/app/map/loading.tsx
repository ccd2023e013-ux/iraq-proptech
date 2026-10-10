import { Skeleton } from "@/components/ui/Skeleton";

/** The map stage while the page loads: the ground first, then the panels. */
export default function Loading() {
  return (
    <div
      role="status"
      aria-busy
      className="relative h-[calc(100dvh-var(--header-h)-var(--tabbar-h))] min-h-[520px] overflow-hidden [--map-top:0.5rem] md:-mt-[var(--header-h)] md:h-dvh md:[--map-top:var(--header-h)]"
    >
      <div className="skeleton absolute inset-0 rounded-none" />
      <div className="surface-modal absolute flex flex-col gap-3 p-4 max-lg:inset-x-2 max-lg:bottom-2 max-lg:rounded-[1.5rem] lg:start-4 lg:top-[calc(var(--map-top)+0.75rem)] lg:bottom-4 lg:w-[392px] lg:rounded-[var(--radius-card)]">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex gap-3 max-lg:hidden">
            <Skeleton className="h-[72px] w-24 shrink-0 rounded-xl" />
            <div className="flex flex-1 flex-col gap-2 pt-1">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3.5 w-3/4" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
