"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
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
  "quality",
];

function StatementRow({ s, dict, locale }: { s: Statement; dict: Dictionary; locale: Locale }) {
  const i = dict.intel;
  return (
    <li className="flex flex-col gap-1 py-3" data-kind={s.kind}>
      <p className={s.kind === "AI_INTERPRETATION" ? "leading-7 text-ink" : "text-ink"}>
        {renderStatement(s, dict, locale)}
      </p>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-3">
        <TrustBadge kind={badgeKind(s.kind)}>{i.kinds[s.kind]}</TrustBadge>
        <span>
          {i.source}: {s.source}
        </span>
        {s.confidence != null && (
          <span className="tabular">
            · {i.confidence} {Math.round(s.confidence * 100)}%
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
      className="rounded-[var(--radius-card)] bg-surface p-6 shadow-soft ring-1 ring-hairline"
      data-testid="intelligence"
    >
      <h2 id="intel-heading" className="font-display text-xl font-semibold tracking-tight text-ink">
        {i.title}
      </h2>
      <p className="mt-1 text-sm text-ink-2">{i.subtitle}</p>

      {!report && (
        <div className="mt-4">
          <Button onClick={analyze} loading={busy} data-testid="intelligence-analyze">
            {busy ? i.analyzing : i.analyze}
          </Button>
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
            className="h-11 min-w-0 flex-1 rounded-full bg-fill px-4 text-ink ring-1 ring-transparent ring-inset placeholder:text-ink-3 focus:bg-surface focus:ring-2 focus:ring-accent focus:outline-none"
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
