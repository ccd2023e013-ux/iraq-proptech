import { Skeleton } from "@/components/ui/Skeleton";

/** Shown instantly while a property loads: same shape as the page. */
export default function Loading() {
  return (
    <div
      role="status"
      aria-busy
      className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8"
    >
      <Skeleton className="aspect-[4/3] w-full rounded-[var(--radius-media)] sm:aspect-[2/1]" />
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-12">
        <div className="flex flex-col gap-3">
          <Skeleton className="h-5 w-24 rounded-[var(--radius-control)]" />
          <Skeleton className="h-10 w-3/4" />
          <Skeleton className="h-5 w-1/2" />
          <div className="mt-4 flex gap-10">
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-12 w-20" />
          </div>
        </div>
        <Skeleton className="h-72 w-full rounded-[var(--radius-card)]" />
      </div>
    </div>
  );
}
