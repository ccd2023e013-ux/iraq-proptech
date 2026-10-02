import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface Usage {
  feature: string;
  provider: string;
  status: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  avg_latency_ms: number;
}

export default async function AiUsagePage() {
  await requirePermission("ai.admin");
  const dict = getDictionary(await getRequestLocale());
  const a = dict.admin;
  const rows = await serverApiFetch<Usage[]>("/api/v1/admin/ai/usage?days=30");
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-brand-900">{a.aiUsage}</h1>
      <div className="overflow-x-auto rounded-[var(--radius-card)] border border-sand-200 bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-sand-200 text-xs text-sand-500">
              <th className="p-2 text-start">{a.feature}</th>
              <th className="p-2 text-start">{a.provider}</th>
              <th className="p-2 text-start">status</th>
              <th className="p-2 text-start">{a.calls}</th>
              <th className="p-2 text-start">{a.tokens}</th>
              <th className="p-2 text-start">{a.latency}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={`${r.feature}-${r.provider}-${r.status}`}
                className="border-b border-sand-100 tabular"
              >
                <td className="p-2 font-mono text-xs" dir="ltr">
                  {r.feature}
                </td>
                <td className="p-2">{r.provider}</td>
                <td className={`p-2 ${r.status === "SUCCEEDED" ? "" : "text-warning"}`}>
                  {r.status}
                </td>
                <td className="p-2">{r.calls}</td>
                <td className="p-2">{r.input_tokens + r.output_tokens}</td>
                <td className="p-2">{r.avg_latency_ms} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
