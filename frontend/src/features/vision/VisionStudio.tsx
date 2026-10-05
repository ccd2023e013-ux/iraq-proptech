"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import { SafeImage } from "@/components/ui/SafeImage";
import { TrustBadge } from "@/components/ui/TrustBadge";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

export interface ConceptOut {
  id: string;
  property_id: string | null;
  brief: Record<string, unknown>;
  provider: string;
  model: string;
  status: "SUCCEEDED" | "FALLBACK";
  label_en: string;
  label_ar: string;
  images: { concept: string; vision: string };
  created_at: string;
}

type Step = "current" | "concept" | "vision";
const TYPES = ["house", "villa", "apartments", "commercial", "mixed_use"] as const;
const STYLES = ["modern", "traditional", "courtyard", "minimal"] as const;

export interface VisionForm {
  building_type: (typeof TYPES)[number];
  floors: number;
  style: (typeof STYLES)[number];
  plot_width_m: number;
  plot_depth_m: number;
  landscaping: boolean;
  parking: boolean;
  pool: boolean;
  shops_ground_floor: boolean;
  notes: string;
}

export const DEFAULT_FORM: VisionForm = {
  building_type: "house",
  floors: 2,
  style: "modern",
  plot_width_m: 15,
  plot_depth_m: 25,
  landscaping: true,
  parking: true,
  pool: false,
  shops_ground_floor: false,
  notes: "",
};

/** Request body for the API: trims notes and clamps numbers to the accepted ranges. */
export function toRequest(form: VisionForm, propertyId: string | null) {
  const clamp = (n: number, lo: number, hi: number) =>
    Math.min(hi, Math.max(lo, Number.isFinite(n) ? n : lo));
  return {
    ...form,
    floors: Math.round(clamp(form.floors, 1, 12)),
    plot_width_m: clamp(form.plot_width_m, 6, 200),
    plot_depth_m: clamp(form.plot_depth_m, 6, 200),
    notes: form.notes.trim() || null,
    property_id: propertyId,
  };
}

function PlotDiagram({ w, d, caption }: { w: number; d: number; caption: string }) {
  const scale = 260 / Math.max(w, d);
  return (
    <figure className="grid h-full place-items-center bg-fill p-6">
      <svg viewBox="0 0 300 300" className="w-full max-w-sm" role="img" aria-label={caption}>
        <rect
          x={150 - (w * scale) / 2}
          y={150 - (d * scale) / 2}
          width={w * scale}
          height={d * scale}
          fill="none"
          stroke="currentColor"
          strokeDasharray="8 6"
          strokeWidth="2.5"
          className="text-gold-500"
        />
      </svg>
      <figcaption className="text-sm text-ink-2 tabular">{caption}</figcaption>
    </figure>
  );
}

export function VisionStudio({
  dict,
  propertyId,
  propertyTitle,
  currentImage,
  recent,
}: {
  dict: Dictionary;
  propertyId: string | null;
  propertyTitle: string | null;
  currentImage: string | null;
  recent: ConceptOut[];
}) {
  const v = dict.vision;
  const [form, setForm] = useState<VisionForm>(DEFAULT_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConceptOut | null>(recent[0] ?? null);
  const [step, setStep] = useState<Step>(recent[0] ? "concept" : "current");

  const set = <K extends keyof VisionForm>(key: K, value: VisionForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const out = await apiFetch<ConceptOut>("/api/v1/vision/concepts", {
        method: "POST",
        body: toRequest(form, propertyId),
      });
      setResult(out);
      setStep("concept");
    } catch (err) {
      setError(describeError(dict, err) || v.error);
    } finally {
      setBusy(false);
    }
  }

  const chip = (active: boolean) =>
    `h-9 rounded-full px-3.5 text-sm font-medium transition ${
      active ? "bg-ink text-surface" : "bg-fill text-ink-2 hover:text-ink"
    }`;
  const label = v.label;

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      <form onSubmit={submit} className="flex flex-col gap-5" data-testid="vision-form">
        {propertyTitle && (
          <p className="rounded-[var(--radius-control)] bg-fill px-4 py-3 text-sm text-ink-2">
            {v.forProperty}: <span className="font-medium text-ink">{propertyTitle}</span>
          </p>
        )}
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink">{v.buildingType}</legend>
          <div className="flex flex-wrap gap-1.5">
            {TYPES.map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={form.building_type === t}
                onClick={() => set("building_type", t)}
                className={chip(form.building_type === t)}
              >
                {v.types[t]}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink">{v.style}</legend>
          <div className="flex flex-wrap gap-1.5">
            {STYLES.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={form.style === s}
                onClick={() => set("style", s)}
                className={chip(form.style === s)}
              >
                {v.styles[s]}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
          <span className="flex justify-between">
            {v.floors}
            <span className="tabular text-ink-2">{form.floors}</span>
          </span>
          <input
            type="range"
            min={1}
            max={12}
            value={form.floors}
            onChange={(e) => set("floors", Number(e.target.value))}
            className="accent-[var(--accent)]"
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          {(
            [
              ["plot_width_m", v.plotWidth],
              ["plot_depth_m", v.plotDepth],
            ] as const
          ).map(([key, text]) => (
            <label key={key} className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              {text}
              <input
                type="number"
                inputMode="decimal"
                min={6}
                max={200}
                value={form[key]}
                onChange={(e) => set(key, Number(e.target.value))}
                className="h-11 rounded-[var(--radius-control)] bg-fill px-3 text-ink tabular ring-1 ring-transparent ring-inset focus:bg-surface focus:ring-2 focus:ring-accent focus:outline-none"
                dir="ltr"
              />
            </label>
          ))}
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink">{v.features}</legend>
          {(
            [
              ["landscaping", v.landscaping],
              ["parking", v.parking],
              ["pool", v.pool],
              ["shops_ground_floor", v.shops],
            ] as const
          ).map(([key, text]) => (
            <label key={key} className="flex items-center justify-between gap-3 text-sm text-ink">
              {text}
              <input
                type="checkbox"
                checked={form[key]}
                onChange={(e) => set(key, e.target.checked)}
                className="size-4 accent-[var(--accent)]"
              />
            </label>
          ))}
        </fieldset>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
          {v.notes}
          <textarea
            value={form.notes}
            maxLength={300}
            rows={2}
            placeholder={v.notesPlaceholder}
            onChange={(e) => set("notes", e.target.value)}
            className="rounded-[var(--radius-control)] bg-fill px-3 py-2 text-ink ring-1 ring-transparent ring-inset placeholder:text-ink-3 focus:bg-surface focus:ring-2 focus:ring-accent focus:outline-none"
          />
        </label>
        <Button type="submit" size="lg" block loading={busy} data-testid="vision-generate">
          {busy ? v.generating : v.generate}
        </Button>
        {error && <p className="text-sm text-danger">{error}</p>}
      </form>

      <section className="flex min-w-0 flex-col gap-3" aria-live="polite">
        <div className="flex rounded-full bg-fill p-1" role="tablist">
          {(["current", "concept", "vision"] as const).map((s) => (
            <button
              key={s}
              type="button"
              role="tab"
              aria-selected={step === s}
              disabled={s !== "current" && !result}
              onClick={() => setStep(s)}
              className={`h-9 flex-1 rounded-full text-sm font-medium transition disabled:opacity-40 ${step === s ? "bg-surface text-ink shadow-soft" : "text-ink-2"}`}
            >
              {v.steps[s]}
            </button>
          ))}
        </div>
        <p
          className="rounded-[var(--radius-control)] bg-ink px-4 py-2 text-center text-xs font-semibold tracking-wide text-surface"
          data-testid="vision-label"
        >
          {label}
        </p>
        <div className="aspect-[8/5] overflow-hidden rounded-[var(--radius-media)] bg-fill">
          {step === "current" &&
            (currentImage ? (
              <SafeImage
                src={currentImage}
                alt={propertyTitle ?? ""}
                fallbackLabel="—"
                className="size-full object-cover"
                loading="eager"
              />
            ) : (
              <PlotDiagram
                w={form.plot_width_m}
                d={form.plot_depth_m}
                caption={v.currentPlot
                  .replace("{w}", String(form.plot_width_m))
                  .replace("{d}", String(form.plot_depth_m))}
              />
            ))}
          {step !== "current" && result && (
            // eslint-disable-next-line @next/next/no-img-element -- private, generated image
            <img
              key={`${result.id}-${step}`}
              src={result.images[step]}
              alt={`${v.steps[step]} — ${label}`}
              className="size-full animate-enter object-contain"
              data-testid={`vision-image-${step}`}
            />
          )}
        </div>
        <p className="text-xs text-ink-3">{v.labelNote}</p>
        {result && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
            <TrustBadge kind="ai">{v.steps.concept}</TrustBadge>
            <span>
              {v.provider}: {result.provider === "mock" ? v.providerMock : result.model}
            </span>
            {result.status === "FALLBACK" && <span className="text-warning">{v.fallback}</span>}
            {step !== "current" && (
              <a
                href={result.images[step]}
                download={`ai-concept-${step}.png`}
                className="ms-auto font-medium text-accent underline-offset-4 hover:underline"
              >
                {v.download}
              </a>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
