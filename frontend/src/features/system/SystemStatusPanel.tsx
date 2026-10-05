import { type BadgeTone, StatusBadge } from "@/components/ui/StatusBadge";
import type { Dictionary } from "@/i18n";
import { errorMessage } from "@/i18n";
import type { CheckStatus, Readiness } from "@/types/system";

const TONE: Record<CheckStatus | Readiness["status"], BadgeTone> = {
  ok: "success",
  degraded: "warning",
  unavailable: "neutral",
  error: "danger",
};

export type SystemStatusResult =
  | { kind: "ok"; readiness: Readiness }
  | { kind: "error"; code: string };

export function SystemStatusPanel({
  result,
  dict,
}: {
  result: SystemStatusResult;
  dict: Dictionary;
}) {
  const s = dict.status;
  return (
    <section
      aria-labelledby="system-status-heading"
      className="rounded-[var(--radius-card)] border border-sand-200 bg-surface p-5 shadow-sm"
    >
      <h2 id="system-status-heading" className="mb-4 text-base font-semibold text-sand-900">
        {s.heading}
      </h2>
      {result.kind === "error" ? (
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-sand-700">{s.api}</span>
          <StatusBadge tone="danger">
            {result.code === "API_NOT_CONFIGURED"
              ? s.notConfigured
              : errorMessage(dict, result.code)}
          </StatusBadge>
        </div>
      ) : (
        <dl className="divide-y divide-sand-100">
          {(
            [
              ["api", result.readiness.status],
              ["database", result.readiness.database.status],
              ["postgis", result.readiness.postgis.status],
              ["redis", result.readiness.redis.status],
            ] as const
          ).map(([key, status]) => (
            <div key={key} className="flex items-center justify-between gap-3 py-2.5">
              <dt className="text-sm text-sand-700">{s[key]}</dt>
              <dd>
                <StatusBadge tone={TONE[status]}>{s[status]}</StatusBadge>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
