"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { TrustBadge } from "@/components/ui/TrustBadge";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type {
  AnswerOut,
  IntelligenceReport,
  Statement,
  StatementSection,
} from "@/types/intelligence";

import { ProviderBadge } from "./ProviderBadge";
import { badgeKind, renderStatement } from "./statements";

const SECTIONS: StatementSection[] = [
  "interpretation",
  "facts",
  "price",
  "neighbourhood",
  "development",
  "quality",
];

const KIND_RAIL: Record<Statement["kind"], string> = {
  FACT: "bg-ink-3",
  SOURCE: "bg-accent-fill",
  ESTIMATE: "bg-gold-500",
  AI_INTERPRETATION: "bg-ink",
  SIMULATION: "bg-gold-500",
};

/**
 * One analysed statement: a thin rail in the colour of its kind, the words,
 * then its label, source and — when known — a small confidence meter.
 */
function StatementRow({ s, dict, locale }: { s: Statement; dict: Dictionary; locale: Locale }) {
  const i = dict.intel;
  const confidence = s.confidence != null ? Math.round(s.confidence * 100) : null;
  return (
    <li className="relative flex flex-col gap-1.5 py-3.5 ps-4" data-kind={s.kind}>
      <span
        aria-hidden
        className={`absolute start-0 top-4 bottom-4 w-0.5 rounded-full opacity-70 ${KIND_RAIL[s.kind] ?? "bg-ink-3"}`}
      />
      <p className={s.kind === "AI_INTERPRETATION" ? "leading-7 text-ink" : "text-ink"}>
        {renderStatement(s, dict, locale)}
      </p>
      <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-ink-3">
        <TrustBadge kind={badgeKind(s.kind)}>{i.kinds[s.kind]}</TrustBadge>
        <span>
          {i.source}: {s.source}
        </span>
        {confidence != null && (
          <span className="inline-flex items-center gap-1.5 tabular">
            {i.confidence}
            <span
              aria-hidden
              className="relative h-1 w-14 overflow-hidden rounded-full bg-fill-strong"
            >
              <span
                className="absolute inset-y-0 start-0 rounded-[var(--radius-control)] bg-accent-fill"
                style={{ width: `${confidence}%` }}
              />
            </span>
            {confidence}%
          </span>
        )}
      </p>
    </li>
  );
}

/**
 * "Is this a good property?" — on demand, every statement labelled FACT /
 * SOURCE / ESTIMATE / AI INTERPRETATION with its source; plus a buyer
 * assistant that answers only from the same evidence.
 */
export function IntelligencePanel({
  dict,
  locale,
  propertyId,
}: {
  dict: Dictionary;
  locale: Locale;
  propertyId: string;
}) {
  const i = dict.intel;
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answers, setAnswers] = useState<{ question: string; out: AnswerOut }[]>([]);

  async function analyze() {
    setBusy(true);
    setError(null);
    try {
      setReport(
        await apiFetch<IntelligenceReport>(
          `/api/v1/ai/properties/${propertyId}/report?language=${locale}`,
        ),
      );
    } catch (err) {
      setError(describeError(dict, err) || i.error);
    } finally {
      setBusy(false);
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const q = question.trim();
    if (q.length < 2) return;
    setAsking(true);
    setError(null);
    try {
      const out = await apiFetch<AnswerOut>(`/api/v1/ai/properties/${propertyId}/ask`, {
        method: "POST",
        body: { question: q, language: locale },
      });
      setAnswers((list) => [{ question: q, out }, ...list].slice(0, 5));
      setQuestion("");
    } catch (err) {
      setError(describeError(dict, err) || i.error);
    } finally {
      setAsking(false);
    }
  }

  return (
    <section
      aria-labelledby="intel-heading"
      className="surface-1 rounded-[var(--radius-card)] p-6"
      data-testid="intelligence"
    >
      <div className="flex items-start gap-3.5">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-fill text-ink">
          <Icon name="insight" className="size-5" />
        </span>
        <div>
          <h2
            id="intel-heading"
            className="font-display text-xl font-semibold tracking-tight text-ink"
          >
            {i.title}
          </h2>
          <p className="mt-1 text-sm text-ink-2">{i.subtitle}</p>
        </div>
      </div>

      {!report && (
        <div className="mt-4">
          <Button onClick={analyze} loading={busy} data-testid="intelligence-analyze">
            {busy ? i.analyzing : i.analyze}
          </Button>
        </div>
      )}
      {busy && !report && (
        <div aria-hidden className="mt-5 flex flex-col gap-3">
          {[0.92, 0.7, 0.84].map((w, n) => (
            <div key={n} className="flex flex-col gap-2 ps-4">
              <Skeleton className="h-3.5" style={{ width: `${w * 100}%` }} />
              <Skeleton className="h-2.5 w-1/3" />
            </div>
          ))}
        </div>
      )}
      {error && <p className="mt-3 text-sm text-danger">{error}</p>}

      {report && (
        <div className="mt-4 flex flex-col gap-6" data-testid="intelligence-report">
          <ProviderBadge dict={dict} provider={report.provider} model={report.model} />
          {SECTIONS.map((section) => {
            const items = report.statements.filter((s) => s.section === section);
            if (items.length === 0) return null;
            return (
              <div key={section}>
                <h3 className="text-sm font-semibold text-ink-2">{i.sections[section]}</h3>
                <ul className="divide-y divide-hairline">
                  {items.map((s, n) => (
                    <StatementRow key={`${s.key}-${n}`} s={s} dict={dict} locale={locale} />
                  ))}
                </ul>
              </div>
            );
          })}
          {report.gaps.length > 0 && (
            <div className="rounded-[var(--radius-control)] bg-fill p-4">
              <h3 className="text-sm font-semibold text-ink">{i.gapsTitle}</h3>
              <ul className="mt-2 flex list-disc flex-col gap-1 ps-5 text-sm text-ink-2">
                {report.gaps.map((g) => (
                  <li key={g}>{(i.gaps as Record<string, string>)[g] ?? g}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-ink-3">{i.disclaimer}</p>
        </div>
      )}

      <form onSubmit={ask} className="mt-6 flex flex-col gap-2 border-t border-hairline pt-5">
        <label htmlFor="intel-question" className="text-sm font-semibold text-ink">
          {i.askTitle}
        </label>
        <div className="flex gap-2">
          <input
            id="intel-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={300}
            placeholder={i.askPlaceholder}
            className="h-11 min-w-0 flex-1 rounded-[var(--radius-control)] bg-fill px-4 text-ink ring-1 ring-transparent ring-inset placeholder:text-ink-3 focus:bg-surface focus:ring-2 focus:ring-accent focus:outline-none"
          />
          <Button type="submit" loading={asking} data-testid="intelligence-ask">
            {i.askButton}
          </Button>
        </div>
        <p className="text-xs text-ink-3">{i.askHint}</p>
        {answers.length > 0 && (
          <ul className="mt-2 flex flex-col gap-4" data-testid="intelligence-answers">
            {answers.map(({ question: q, out }, n) => (
              <li key={n} className="rounded-[var(--radius-control)] bg-fill p-4">
                <p className="text-sm font-medium text-ink-2">“{q}”</p>
                <ul className="divide-y divide-hairline">
                  <StatementRow s={out.answer} dict={dict} locale={locale} />
                  {out.statements.slice(0, 4).map((s, k) => (
                    <StatementRow key={`${s.key}-${k}`} s={s} dict={dict} locale={locale} />
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </form>
    </section>
  );
}
