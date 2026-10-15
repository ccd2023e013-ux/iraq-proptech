"use client";

import Link from "next/link";
import { useState } from "react";

import { TrustBadge } from "@/components/ui/TrustBadge";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { formatCompactPrice } from "@/lib/format";

type Scenario = "keep" | "addFloors" | "apartments";

export interface ApartmentMedian {
  perM2: number;
  currency: "IQD" | "USD";
  listings: number;
  demo: boolean;
  area: string;
}

/**
 * Future Property scenarios: three ways to read a plot's potential, computed in
 * the open. Facts come from the listing; assumptions are the reader's own
 * (sliders, starting at neutral values, never presented as regulations); the
 * projection is arithmetic on both, plus the market's apartment median where
 * one exists — labelled as an estimate, with its sample and demo status.
 */
export function FutureScenarios({
  dict,
  locale,
  propertyId,
  plotM2,
  floorsNow,
  median,
}: {
  dict: Dictionary;
  locale: Locale;
  propertyId: string;
  plotM2: number;
  floorsNow: number | null;
  median: ApartmentMedian | null;
}) {
  const t = dict.scenarios;
  const [scenario, setScenario] = useState<Scenario>("apartments");
  const [coverage, setCoverage] = useState(60);
  const [floors, setFloors] = useState(Math.max(2, (floorsNow ?? 1) + 2));
  const [unit, setUnit] = useState(120);
  const [cost, setCost] = useState("");

  const effectiveFloors =
    scenario === "keep" ? (floorsNow ?? 1) : scenario === "addFloors" ? floors : floors;
  const gfa = Math.round(plotM2 * (coverage / 100) * effectiveFloors);
  const units = scenario === "apartments" ? Math.floor((gfa * 0.82) / unit) : null;
  const costNum = Number(cost.replace(/[^\d.]/g, ""));
  const buildCost =
    scenario !== "keep" && costNum > 0
      ? (scenario === "addFloors"
          ? Math.max(0, gfa - plotM2 * (coverage / 100) * (floorsNow ?? 1))
          : gfa) * costNum
      : null;
  const sales = scenario === "apartments" && units && median ? units * unit * median.perM2 : null;
  const n = (v: number) => v.toLocaleString(locale === "ar" ? "ar-IQ-u-nu-latn" : "en-US");
  const money = (v: number) => formatCompactPrice(v, median?.currency ?? "IQD", locale) ?? "—";

  const slider = (
    label: string,
    value: number,
    set: (v: number) => void,
    min: number,
    max: number,
    step: number,
    suffix: string,
  ) => (
    <label className="flex flex-col gap-1.5">
      <span className="flex justify-between text-sm text-ink-2">
        {label}
        <span className="font-medium text-ink tabular">
          {n(value)}
          {suffix}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => set(Number(e.target.value))}
      />
    </label>
  );

  return (
    <div className="flex flex-col gap-6" data-testid="future-scenarios">
      <div className="seg w-fit" role="group">
        {(["keep", "addFloors", "apartments"] as const).map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={scenario === s}
            onClick={() => setScenario(s)}
          >
            {t[s]}
          </button>
        ))}
      </div>

      <div className="grid gap-px overflow-hidden rounded-[var(--radius-card)] bg-hairline md:grid-cols-3">
        <section className="flex flex-col gap-3 bg-surface p-5">
          <p className="flex items-center gap-2">
            <TrustBadge kind="fact">{t.facts}</TrustBadge>
          </p>
          <dl className="flex flex-col gap-2 text-[15px]">
            <div className="flex justify-between gap-3">
              <dt className="text-ink-2">{t.plotArea}</dt>
              <dd className="font-medium text-ink tabular">{n(plotM2)} m²</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-2">{t.currentFloors}</dt>
              <dd className="font-medium text-ink tabular">{floorsNow ?? t.notGiven}</dd>
            </div>
          </dl>
        </section>

        <section className="flex flex-col gap-4 bg-surface p-5">
          <p>
            <TrustBadge kind="estimate">{t.assumptions}</TrustBadge>
          </p>
          {scenario !== "keep" && slider(t.coverage, coverage, setCoverage, 30, 90, 5, "%")}
          {scenario !== "keep" && slider(t.floors, floors, setFloors, 1, 12, 1, "")}
          {scenario === "apartments" && slider(t.unitSize, unit, setUnit, 60, 250, 10, " m²")}
          {scenario !== "keep" && (
            <label className="flex flex-col gap-1.5">
              <span className="text-sm text-ink-2">{t.costPerM2}</span>
              <input
                inputMode="numeric"
                value={cost}
                onChange={(e) => setCost(e.target.value)}
                placeholder="—"
                className="field h-10"
                dir="ltr"
              />
            </label>
          )}
        </section>

        <section className="flex flex-col gap-3 bg-surface p-5">
          <p>
            <TrustBadge kind="simulation">{t.projection}</TrustBadge>
          </p>
          <dl className="flex flex-col gap-3">
            <div>
              <dt className="meta">{t.gfa}</dt>
              <dd className="kpi text-3xl text-ink">{n(gfa)} m²</dd>
            </div>
            {units !== null && (
              <div>
                <dt className="meta">{t.units}</dt>
                <dd className="kpi text-2xl text-ink">{n(units)}</dd>
              </div>
            )}
            {buildCost !== null && (
              <div>
                <dt className="meta">{t.buildCost}</dt>
                <dd className="kpi text-xl text-ink">{money(buildCost)}</dd>
              </div>
            )}
            {sales !== null && (
              <div>
                <dt className="meta">{t.salesValue}</dt>
                <dd className="kpi text-xl text-ink">≈ {money(sales)}</dd>
              </div>
            )}
          </dl>
        </section>
      </div>

      <div className="flex flex-col gap-2 text-sm">
        {scenario === "apartments" &&
          (median ? (
            <p className="text-ink-2">
              {t.medianSource
                .replace("{area}", median.area)
                .replace("{value}", money(median.perM2))
                .replace("{n}", n(median.listings))
                .replace("{demo}", median.demo ? t.demoNote : "")}
            </p>
          ) : (
            <p className="text-ink-2">{t.noMedian}</p>
          ))}
        <p className="caption">{t.disclaimer}</p>
        <Link href={`/properties/${propertyId}/flight`} className="link w-fit font-medium">
          {t.concept}: {t.seeMassing}
        </Link>
      </div>
    </div>
  );
}
