import { Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div
      role="status"
      aria-busy
      className="mx-auto grid max-w-7xl gap-4 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(320px,420px)_1fr]"
    >
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-[var(--radius-card)]" />
        ))}
      </div>
      <Skeleton className="h-[70vh] w-full rounded-[var(--radius-media)]" />
    </div>
  );
}
