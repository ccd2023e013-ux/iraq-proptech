import { CardSkeleton, Skeleton } from "@/components/ui/Skeleton";

/** Shown instantly while the search results load. */
export default function Loading() {
  return (
    <div
      role="status"
      aria-busy
      className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6"
    >
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-12 w-full rounded-[var(--radius-control)]" />
      <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
