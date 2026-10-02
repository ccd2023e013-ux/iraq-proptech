import { Card } from "@/components/ui/Card";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { serverApiFetch } from "@/lib/api/server";
import { formatPrice } from "@/lib/format";
import type { AIEnvelope, InvestmentResult, PriceResult } from "@/types/ai";

function Explain({
  dict,
  envelope,
}: {
  dict: Dictionary;
  envelope: Pick<AIEnvelope, "methodology" | "limitations">;
}) {
  return (
    <details className="mt-3 text-xs text-sand-500">
      <summary className="cursor-pointer">{dict.ai.methodology}</summary>
      <p className="mt-1">{envelope.methodology}</p>
      {envelope.limitations.length > 0 && (
        <>
          <p className="mt-2 font-medium">{dict.ai.limitations}</p>
          <ul className="list-disc ps-4">
            {envelope.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </>
      )}
    </details>
  );
}

function unavailable(dict: Dictionary, reason: string | undefined): string {
  return (reason && dict.ai.unavailable[reason as keyof Dictionary["ai"]["unavailable"]]) || "—";
}

/** Estimates computed from platform data, always labelled as estimates. */
export async function Insights({
  propertyId,
  purpose,
  dict,
  locale,
}: {
  propertyId: string;
  purpose: string;
  dict: Dictionary;
  locale: Locale;
}) {
  const a = dict.ai;
  const [price, investment] = await Promise.all([
    serverApiFetch<AIEnvelope<PriceResult>>(
      `/api/v1/ai/properties/${propertyId}/price-analysis`,
    ).catch(() => null),
    purpose === "SALE"
      ? serverApiFetch<AIEnvelope<InvestmentResult>>(
          `/api/v1/ai/properties/${propertyId}/investment`,
        ).catch(() => null)
      : Promise.resolve(null),
  ]);
  if (!price) return null;
  const p = price.result;
  const money = (v: string | null) => (v ? formatPrice(v, p.currency, locale) : "—");

  return (
    <Card title={`${a.insights} · ${a.estimate}`}>
      <div className="flex flex-col gap-4">
        <section aria-label={a.priceAnalysis}>
          <h3 className="text-sm font-semibold text-sand-900">
            {a.priceAnalysis}
            <span className="ms-2 rounded bg-gold-100 px-1.5 py-0.5 text-[11px] font-medium text-gold-700">
              {a.estimate}
            </span>
          </h3>
          {p.value ? (
            <dl className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-sand-500">{a.estimatedValue}</dt>
                <dd className="font-semibold tabular">{money(p.value)}</dd>
              </div>
              <div>
                <dt className="text-xs text-sand-500">{a.range}</dt>
                <dd className="tabular">
                  {money(p.low)} – {money(p.high)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-sand-500">{a.perM2}</dt>
                <dd className="tabular">{money(p.price_per_m2_median)}</dd>
              </div>
              <div>
                <dt className="text-xs text-sand-500">{a.confidence}</dt>
                <dd className="tabular">
                  {price.confidence !== null ? `${Math.round(price.confidence * 100)}%` : "—"} ·{" "}
                  {p.comparable_count} {a.comparables}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="mt-1 text-sm text-sand-500">{unavailable(dict, p.unavailable_reason)}</p>
          )}
          {p.asking_price_position && (
            <p className="mt-2 text-sm text-sand-700">{a.position[p.asking_price_position]}</p>
          )}
          {price.disclaimer && <p className="mt-2 text-xs text-warning">{price.disclaimer}</p>}
          <Explain dict={dict} envelope={price} />
        </section>
        {investment && (
          <section aria-label={a.investment} className="border-t border-sand-100 pt-3">
            <h3 className="text-sm font-semibold text-sand-900">{a.investment}</h3>
            {investment.result.gross_yield_percent ? (
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-sand-500">{a.grossYield}</dt>
                  <dd className="font-semibold tabular">
                    {investment.result.gross_yield_percent}%
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-sand-500">{a.monthlyRent}</dt>
                  <dd className="tabular">
                    {formatPrice(
                      investment.result.estimated_monthly_rent,
                      investment.result.currency,
                      locale,
                    )}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="mt-1 text-sm text-sand-500">
                {unavailable(dict, investment.result.unavailable_reason)}
              </p>
            )}
            <Explain dict={dict} envelope={investment} />
          </section>
        )}
      </div>
    </Card>
  );
}
